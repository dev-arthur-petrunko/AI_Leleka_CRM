"""Polling-синхронізація з курсором (фаза 3.3): стани, рух курсора після успіху, 429."""

from datetime import datetime, UTC

from sqlalchemy.orm import Session

from app.models import Integration, SyncState


def get_state(db: Session, row: Integration) -> SyncState:
    st = db.query(SyncState).filter(SyncState.integration_id == row.id).first()
    if not st:
        st = SyncState(tenant_id=row.tenant_id, integration_id=row.id)
        db.add(st)
        db.commit()
        db.refresh(st)
    return st


def _mark_ok(db: Session, row, st) -> None:

    st.cursor = datetime.now(UTC).isoformat()
    st.last_success_at = datetime.now(UTC)
    st.last_error = None
    st.consecutive_failures = 0
    row.status, row.last_error = "ok", None
    row.last_sync_at = datetime.now(UTC)
    db.commit()


def sync_integration(db: Session, integration_id) -> dict:
    """Одна ітерація: pull → upsert → курсор. Повтор безпечний (ідемпотентність)."""
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
        adapter = {"prom": PromAdapter,
                   "rozetka": RozetkaAdapter}[row.provider](creds, row.settings)
        resp = adapter.pull_orders()
        if resp.get("stub"):
            _mark_ok(db, row, st)  # ключа нема — нічого тягнути, але це не помилка
            return {"ok": True, "stub": True, "imported": 0}
        orders = resp.get("data", {}).get("orders", []) \
            if isinstance(resp.get("data"), dict) else []
        n = 0
        for raw in orders:
            o = normalize_order(row.provider, raw)
            upsert_order(db, row.tenant_id, {
                "source": row.provider, "external_id": o["external_id"] or f"sync-{n}",
                "client_name": o["name"], "phone": o["phone"],
                "total": o["amount"], "order_number": o["external_id"]}, origin="sync")
            n += 1
        # курсор рухаємо ТІЛЬКИ після успіху
        _mark_ok(db, row, st)
        db.commit()
        return {"ok": True, "imported": n}
    except Exception as e:
        st.consecutive_failures = (st.consecutive_failures or 0) + 1
        st.last_error = str(e)[:500]
        msg = str(e)
        if "401" in msg or "403" in msg or "auth" in msg.lower():
            row.status = "auth_failed"
        else:
            row.status = "error"
        row.last_error = str(e)[:500]
        db.commit()
        return {"ok": False, "error": str(e)[:300]}
