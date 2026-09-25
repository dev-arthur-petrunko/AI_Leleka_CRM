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

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Client, Deal, Task

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
    """Клієнти без активності N днів — ризик відтоку."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=idle_days)
    # остання активність клієнта = max(last_activity_at його угод)
    deals = db.query(Deal).filter(Deal.tenant_id == tenant_id).all()
    last_by_client: dict[str, datetime] = {}
    for d in deals:
        key = str(d.client_id)
        if key not in last_by_client or d.last_activity_at > last_by_client[key]:
            last_by_client[key] = d.last_activity_at
    out = []
    for cid, last in last_by_client.items():
        # ensure tz-aware compare
        last_aware = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
        if last_aware < cutoff:
            client = db.query(Client).filter(
                Client.id == cid, Client.tenant_id == tenant_id).first()
            if client and client.segment != "lost":
                out.append({"client_id": cid, "name": client.name,
                            "days_idle": (datetime.now(timezone.utc) - last_aware).days,
                            "segment": client.segment})
    return sorted(out, key=lambda x: x["days_idle"], reverse=True)[:20]


def next_best_actions(db: Session, tenant_id: UUID) -> list[dict]:
    """Черга менеджеру: спочатку завислі, потім гарячі без задач."""
    cutoff_3d = datetime.now(timezone.utc) - timedelta(days=3)
    stuck = db.query(Deal).filter(
        Deal.tenant_id == tenant_id,
        Deal.stage.notin_(["won", "lost"]),
        Deal.last_activity_at < cutoff_3d).limit(10).all()
    actions = [{"priority": 1, "action": "call_now", "deal_id": str(d.id),
                "reason": f"зависла { _days_since(d.last_activity_at)} дн., stage={d.stage}"}
               for d in stuck]
    # гарячі без відкритих задач
    open_deal_ids = {t.deal_id for t in db.query(Task).filter(
        Task.tenant_id == tenant_id, Task.status == "open").all() if t.deal_id}
    hot = [d for d in db.query(Deal).filter(
        Deal.tenant_id == tenant_id, Deal.stage == "negotiation").limit(20).all()
        if d.id not in open_deal_ids][:5]
    actions += [{"priority": 2, "action": "create_followup", "deal_id": str(d.id),
                 "reason": "переговори без відкритої задачі"} for d in hot]
    return actions


def ai_text_insight(anonymized: list[dict]) -> dict:
    """PRO-рівень: сюди підключається Claude/OpenAI API.

    MVP повертає шаблонний insight без зовнішніх викликів.
    Прод: requests.post(CLAUDE_API, json={aggregates: anonymized})
    """
    total = sum(d["amount"] for d in anonymized)
    n = len(anonymized)
    return {"summary": f"Угод в роботі: {n}, сума пайплайна: {total:.0f} грн. "
                       f"Підключіть ANTHROPIC_API_KEY для текстового розбору Claude.",
            "pii_sent": False}


def _days_since(dt: datetime | None) -> int:
    if not dt:
        return 999
    aware = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - aware).days)
