"""AI-аналітика MVP.

Два рівні (за ТЗ п.6.2):
1. Базовий — евристики БЕЗ зовнішнього API (працює одразу, без ключів).
2. PRO — знеособлені агрегати -> Claude/OpenAI API для текстового insight.
   PII (phone/email/name) НІКОЛИ не йде в зовнішній AI (GDPR).

Що рахує (п.6.1):
- lead scoring: hot/warm/cold + 0-100
- forecast: прогноз доходу на наступний місяць (moving average)
- churn: ризик відтоку (давно без активності)
- loss reasons: групування програних угод
- next best action: кому дзвонити зараз
"""

from datetime import datetime, timedelta, UTC
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Client, Deal

STAGE_WEIGHT = {"new": 20, "contacted": 40, "negotiation": 70, "won": 100, "lost": 0}


def anonymize_deals(deals: list[Deal]) -> list[dict]:
    """Тільки агрегати для зовнішнього AI: без PII."""
    return [
        {"stage": d.stage, "amount": float(d.amount or 0),
         "probability": d.probability,
         "days_since_activity": _days_since(d.last_activity_at)}
        for d in deals
    ]


def score_deal(deal: Deal, client: Client | None = None) -> dict:
    """Lead scoring 0-100. Пояснювано, без ML-залежностей (MVP)."""
    base = STAGE_WEIGHT.get(deal.stage, 0)
    # свіжість активності: +15 якщо активність <24г, +5 якщо <3д
    days = _days_since(deal.last_activity_at)
    freshness = 15 if days <= 1 else (5 if days <= 3 else 0)
    # сума: +до 15 (нормуємо на 100k грн)
    amount_bonus = min(15, float(deal.amount or 0) / 100_000 * 15)
    # сегмент клієнта
    seg_bonus = {"vip": 10, "regular": 5}.get((client.segment if client else ""), 0)
    score = max(0, min(100, round(base + freshness + amount_bonus + seg_bonus)))
    label = "hot" if score >= 70 else ("warm" if score >= 40 else "cold")
    # ручна температура клієнта сильніша за авто-скоринг
    manual = ((getattr(client, "temperature", None) or "").strip().lower()
              if client else "")
    if manual == "hot":
        score, label = max(score, 70), "hot"
    elif manual == "warm":
        score, label = min(69, max(40, score)), "warm"
    elif manual == "cold":
        score, label = min(score, 39), "cold"
    return {"deal_id": str(deal.id), "score": score, "label": label,
            "reasons": {"stage": deal.stage, "days_idle": days,
                        "amount": float(deal.amount or 0)}}


def forecast_revenue(deals_won_by_month: list[dict]) -> dict:
    """Moving average за 3 міс. deals_won_by_month: [{month, total}]."""
    totals = [m["total"] for m in deals_won_by_month[-3:]]
    if not totals:
        return {"forecast_next_month": 0, "method": "no_data"}
    forecast = round(sum(totals) / len(totals), 2)
    return {"forecast_next_month": forecast, "method": f"avg_last_{len(totals)}",
            "history": deals_won_by_month[-6:]}


def churn_candidates(db: Session, tenant_id: UUID, idle_days: int = 30) -> list[dict]:
    """Клієнти без активності N днів — ОДИН SQL-запит замість N+1 (фаза 6.1)."""
    from sqlalchemy import text

    rows = db.execute(text(
        "SELECT c.id, c.name, c.segment, MAX(d.last_activity_at) AS last_act "
        "FROM clients c JOIN deals d ON d.client_id = c.id AND d.tenant_id = c.tenant_id "
        "WHERE c.tenant_id = :t AND c.segment <> 'lost' AND c.deleted_at IS NULL "
        "GROUP BY c.id, c.name, c.segment "
        "HAVING MAX(d.last_activity_at) < now() - make_interval(days => :days) "
        "ORDER BY last_act LIMIT 20"),
        {"t": str(tenant_id), "days": idle_days}).fetchall()
    now = datetime.now(UTC)
    return [{"client_id": str(r[0]), "name": r[1], "segment": r[2],
             "days_idle": max(0, (now - r[3].replace(tzinfo=UTC)).days
                              if r[3].tzinfo is None else (now - r[3]).days)}
            for r in rows]


def next_best_actions(db: Session, tenant_id: UUID) -> list[dict]:
    """Черга менеджеру: завислі + переговори без задач (2 запити замість 3 таблиць цілком)."""
    from sqlalchemy import text

    cutoff_3d = datetime.now(UTC) - timedelta(days=3)
    stuck = db.execute(text(
        "SELECT id, stage, last_activity_at FROM deals WHERE tenant_id = :t "
        "AND stage NOT IN ('won','lost') AND last_activity_at < :cut "
        "ORDER BY last_activity_at LIMIT 10"),
        {"t": str(tenant_id), "cut": cutoff_3d}).fetchall()
    actions = [{"priority": 1, "action": "call_now", "deal_id": str(r[0]),
                "reason": f"зависла {_days_since(r[2])} дн., stage={r[1]}"}
               for r in stuck]
    hot = db.execute(text(
        "SELECT d.id FROM deals d WHERE d.tenant_id = :t AND d.stage = 'negotiation' "
        "AND NOT EXISTS (SELECT 1 FROM tasks t WHERE t.deal_id = d.id "
        "AND t.tenant_id = :t AND t.status = 'open') LIMIT 5"),
        {"t": str(tenant_id)}).fetchall()
    actions += [{"priority": 2, "action": "create_followup", "deal_id": str(r[0]),
                 "reason": "переговори без відкритої задачі"} for r in hot]
    return actions


def ai_text_insight(anonymized: list[dict]) -> dict:
    """PRO: реальний Claude, якщо є ANTHROPIC_API_KEY; інакше — шаблон.
    PII ніколи не відправляється (тільки агрегати, pii_sent=False)."""
    import os

    total = sum(d["amount"] for d in anonymized)
    n = len(anonymized)
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
    if not key:
        return {"summary": f"Угод в роботі: {n}, сума пайплайна: {total:.0f} грн. "
                           f"Підключіть ANTHROPIC_API_KEY для текстового розбору Claude.",
                "pii_sent": False, "ai_used": False}
    try:
        import requests
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": model, "max_tokens": 300, "messages": [{
                "role": "user",
                "content": f"Коротко (3 речення, українською) проаналізуй воронку: угод {n}, "
                           f"сума {total:.0f} грн. Дані знеособлені."}]},
            timeout=20)
        r.raise_for_status()
        return {"summary": r.json()["content"][0]["text"],
                "pii_sent": False, "ai_used": True, "model": model}
    except Exception as e:
        return {"summary": f"Угод: {n}, сума: {total:.0f} грн. (AI недоступний: {e})",
                "pii_sent": False, "ai_used": False}


def _days_since(dt: datetime | None) -> int:
    if not dt:
        return 999
    aware = dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    return max(0, (datetime.now(UTC) - aware).days)
