"""Inbox вебхуков: принимаем быстро, обрабатываем воркером с ретраями.

POST /webhooks/{provider} — Prom/Rozetka/NP шлют сюда.
Идемпотентность по (provider, external_id). Повторы: next_retry_at + retry_count.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Tenant, WebhookEvent

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/{provider}")
async def ingest(provider: str, request: Request, db: Session = Depends(get_db)):
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    # tenant определяем по токену/подписи провайдера; MVP: slug в query
    slug = request.query_params.get("tenant")
    tenant = db.query(Tenant).filter(Tenant.slug == slug).first() if slug else None
    external_id = str(body.get("id") or body.get("order_id") or body.get("external_id") or "")

    existing = db.query(WebhookEvent).filter(
        WebhookEvent.provider == provider, WebhookEvent.external_id == external_id
    ).first() if external_id else None
    if existing:
        return {"ok": True, "deduplicated": True, "id": str(existing.id)}

    ev = WebhookEvent(
        tenant_id=tenant.id if tenant else None,
        provider=provider,
        external_id=external_id or None,
        payload=body if isinstance(body, dict) else {"raw": str(body)},
    )
    db.add(ev)
    db.commit()
    return {"ok": True, "id": str(ev.id)}


@router.get("/pending")
def pending(db: Session = Depends(get_db)):
    """Для воркера: что пора повторить."""
    from datetime import datetime, timezone
    return db.query(WebhookEvent).filter(
        WebhookEvent.status.in_(["received", "failed"]),
        WebhookEvent.next_retry_at <= datetime.now(timezone.utc),
    ).order_by(WebhookEvent.next_retry_at).limit(50).all()
