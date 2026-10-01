# -*- coding: utf-8 -*-
"""Періодичні задачі (фаза 3): вебхуки, sync, трекінг НП, stuck, білінг, фіди."""

from datetime import datetime, timedelta, timezone

from app.workers.celery_app import celery


@celery.task(name="leleka.process_webhook_batch")
def process_webhook_batch(limit: int = 50) -> dict:
    """Пачка подій: SKIP LOCKED, upsert_order, ретраї з backoff, dead після 10 спроб."""
    from sqlalchemy import text

    from app.db.session import SessionLocal
    from app.services.orders import upsert_order

    db = SessionLocal()
    done, failed, dead = 0, 0, 0
    try:
        rows = db.execute(text(
            "SELECT id FROM webhook_events "
            "WHERE status IN ('received','failed') AND next_retry_at <= now() "
            "ORDER BY next_retry_at LIMIT :lim FOR UPDATE SKIP LOCKED"),
            {"lim": limit}).fetchall()
        from app.models import WebhookEvent

        for (wid,) in rows:
            ev = db.query(WebhookEvent).filter(WebhookEvent.id == wid).first()
            if not ev:
                continue
            try:
                ev.status = "processing"
                db.commit()
                body = ev.payload or {}
                upsert_order(db, ev.tenant_id, {
                    "source": ev.provider, "external_id": ev.external_id,
                    "client_name": body.get("client_name", ""),
                    "phone": body.get("phone") or body.get("client_phone"),
                    "email": body.get("email"),
                    "total": float(body.get("total") or body.get("price") or 0),
                    "raw": body}, origin="webhook")
                ev.status = "processed"
                done += 1
            except Exception as e:  # noqa: BLE001
                ev.retry_count = (ev.retry_count or 0) + 1
                if ev.retry_count >= 10:
                    ev.status = "dead"
                    dead += 1
                else:
                    ev.status = "failed"
                    ev.error = str(e)[:500]
                    minutes = min(2 ** ev.retry_count, 60)
                    ev.next_retry_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)
                    failed += 1
            db.commit()
        return {"done": done, "failed": failed, "dead": dead}
    finally:
        db.close()


@celery.task(name="leleka.sync_due_integrations")
def sync_due_integrations() -> list:
    """Polling з курсором: sync_state на інтеграцію, рух курсора після успіху."""
    from app.db.session import SessionLocal
    from app.models import Integration
    from app.services.sync import sync_integration

    db = SessionLocal()
    try:
        out = []
        for row in db.query(Integration).filter(Integration.is_active.is_(True)).all():
            if row.provider in ("prom", "rozetka"):
                out.append(sync_integration(db, row.id))
        return out
    finally:
        db.close()


@celery.task(name="leleka.run_stuck_check")
def run_stuck_check() -> dict:
    from app.workers.stuck_checker import check_stuck
    return check_stuck()


@celery.task(name="leleka.run_billing_recalc")
def run_billing_recalc() -> list:
    from app.workers.billing_recalc import recalc
    return recalc()


@celery.task(name="leleka.run_feed_scheduler")
def run_feed_scheduler() -> list:
    from app.workers.feed_scheduler import run_due
    return run_due()


@celery.task(name="leleka.run_np_poll")
def run_np_poll() -> dict:
    from app.services.shipments import poll_shipments
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        return poll_shipments(db)
    finally:
        db.close()
