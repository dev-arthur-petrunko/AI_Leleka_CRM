"""Polling-синхронізація з курсором (фаза 3.3): стани, рух курсора після успіху, 429.

Правила:
- тягнемо від курсора (ISO-дата останнього ОБРОБЛЕНОГО замовлення), пачками до 100,
  максимум 10 ітерацій; стоп — коротка сторінка або жодного нового external_id;
- курсор — дата останнього замовлення, НЕ «зараз» (інакше пропускаємо);
- без номера — стабільний sync-<sha16 від тіла>, а не sync-<n> (інакше дублі);
- позиції передаємо в upsert_order;
- провал запиту (вкл. 429) — курсор НЕ рухаємо, пишемо помилку;
- без ключа — статус not_connected, а не ok.
"""

import hashlib
import json
from datetime import datetime, UTC

from sqlalchemy.orm import Session

from app.models import Integration, SyncState

PAGE_LIMIT = 100
MAX_PAGES = 10

# кандидати полів дати в сирих відповідях (провайдери називають по-різному)
DATE_KEYS = ("date_created", "created_at", "created", "date", "date_modified")


def get_state(db: Session, row: Integration) -> SyncState:
    st = db.query(SyncState).filter(SyncState.integration_id == row.id).first()
    if not st:
        st = SyncState(tenant_id=row.tenant_id, integration_id=row.id)
        db.add(st)
        db.commit()
        db.refresh(st)
    return st


def stable_external_id(provider: str, raw: dict, index: int) -> str:
    ext = str(raw.get("id") or raw.get("order_id") or raw.get("external_id") or "")
    if ext and ext != "0":
        return ext
    h = hashlib.sha256(json.dumps(
        {"p": provider, "raw": raw, "i": index},
        sort_keys=True, default=str).encode()).hexdigest()[:16]
    return f"sync-{h}"


def order_date(raw: dict) -> str | None:
    for k in DATE_KEYS:
        v = raw.get(k)
        if v:
            return str(v)
    return None


def _mark_ok(db: Session, row, st, cursor: str | None) -> None:
    if cursor:
        st.cursor = cursor
    st.last_success_at = datetime.now(UTC)
    st.last_error = None
    st.consecutive_failures = 0
    row.status, row.last_error = "ok", None
    row.last_sync_at = datetime.now(UTC)
    db.commit()


def _mark_fail(db: Session, row, st, err: str) -> dict:
    st.consecutive_failures = (st.consecutive_failures or 0) + 1
    st.last_error = err[:500]
    msg = err.lower()
    if "401" in msg or "403" in msg or "auth" in msg:
        row.status = "auth_failed"
    else:
        row.status = "error"
    row.last_error = err[:500]
    db.commit()
    return {"ok": False, "error": err[:300]}


def sync_integration(db: Session, integration_id) -> dict:
    """Одна ітерація: pull від курсора → upsert → курсор. Повтор безпечний."""
    from app.core.security import decrypt_credentials
    from app.integrations.marketplace import (
        PromAdapter,
        RozetkaAdapter,
        normalize_order,
    )
    from app.services.orders import upsert_order

    row = db.query(Integration).filter(Integration.id == integration_id).first()
    if not row or not row.is_active:
        return {"ok": False, "error": "inactive"}
    st = get_state(db, row)
    try:
        creds = decrypt_credentials(row.credentials)
    except Exception:
        creds = {}
    adapter = {"prom": PromAdapter,
               "rozetka": RozetkaAdapter}.get(row.provider)
    if adapter is None:
        return _mark_fail(db, row, st, f"unknown provider {row.provider}")
    adapter = adapter(creds, row.settings)
    if not adapter.configured:
        row.status, row.last_error = "not_connected", "Додайте ключ в інтеграціях"
        db.commit()
        return {"ok": False, "error": "not_connected", "stub": True}
    cursor = st.cursor  # ISO-дата останнього обробленого (НЕ «зараз»)
    seen: set[str] = set()
    max_date = cursor
    total = 0
    try:
        for _ in range(MAX_PAGES):
            resp = adapter.pull_orders(limit=PAGE_LIMIT, date_from=max_date)
            if not resp.get("ok"):
                err = str(resp.get("error") or "pull failed")
                if "429" in err:
                    err = "429 rate limited провайдером — пауза до наступного циклу"
                return _mark_fail(db, row, st, err)
            data = resp.get("data")
            orders = data.get("orders", []) if isinstance(data, dict) else []
            if not orders:
                break
            fresh = 0
            for i, raw in enumerate(orders):
                if not isinstance(raw, dict):
                    continue
                ext = stable_external_id(row.provider, raw, total + i)
                if ext in seen:
                    continue
                seen.add(ext)
                o = normalize_order(row.provider, raw)
                upsert_order(db, row.tenant_id, {
                    "source": row.provider, "external_id": ext,
                    "client_name": o["name"], "phone": o["phone"],
                    "total": o["amount"], "order_number": o["external_id"] or ext,
                    "items": o.get("items") or [], "raw": raw}, origin="sync")
                total += 1
                fresh += 1
                d = order_date(raw)
                if d and (not max_date or d > max_date):
                    max_date = d
            if len(orders) < PAGE_LIMIT or fresh == 0:
                break
        # курсор рухаємо ТІЛЬКИ вперед і ТІЛЬКИ після успіху
        _mark_ok(db, row, st, max_date if max_date != cursor else None)
        db.commit()
        return {"ok": True, "imported": total}
    except Exception as e:
        return _mark_fail(db, row, st, str(e))
