"""Inbox вебхуков (фаза 1: безпека).

- POST /webhooks/{provider} — legacy-маршрут (slug у query). Залишено для сумісності;
  для нових інтеграцій використовуйте підписаний /{provider}/{integration_id}.
- POST /webhooks/{provider}/{integration_id} — тенант за integration_id, перевірка
  секрету (заголовок X-Webhook-Secret або ?secret=) або HMAC-підпису тіла
  (X-Signature). Ліміт тіла 1 МБ + rate-limit.
- Дедуп: UNIQUE(tenant_id, provider, external_id); порожній external_id → sha256 тіла.
- GET /webhooks/pending — ТІЛЬКИ owner/admin свого тенанта (воркер читає БД напряму).
"""

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.core.rate import limiter
from app.core.security import decrypt_credentials, verify_signature
from app.db.session import get_db
from app.models import Integration, Tenant, User, WebhookEvent

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_owner_admin = require_role("owner", "admin")
MAX_BODY_BYTES = 1024 * 1024


def _external_id(body: dict, raw: bytes) -> str:
    ext = str(body.get("id") or body.get("order_id") or body.get("external_id") or "")
    if ext:
        return ext
    return "sha256:" + hashlib.sha256(raw).hexdigest()  # фаза 1.3


def _store(db: Session, tenant_id, provider: str, external_id: str, payload: dict):
    existing = db.query(WebhookEvent).filter(
        WebhookEvent.tenant_id == tenant_id, WebhookEvent.provider == provider,
        WebhookEvent.external_id == external_id).first()
    if existing:
        return {"ok": True, "deduplicated": True, "id": str(existing.id)}
    ev = WebhookEvent(tenant_id=tenant_id, provider=provider,
                      external_id=external_id, payload=payload)
    db.add(ev)
    db.commit()
    return {"ok": True, "id": str(ev.id)}


@router.post("/{provider}")
async def ingest(provider: str, request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(413, "Тіло завелике")
    try:
        import json
        body = json.loads(raw) if raw else {}
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {"raw": str(body)[:2000]}
    slug = request.query_params.get("tenant")
    tenant = db.query(Tenant).filter(Tenant.slug == slug).first() if slug else None
    if not tenant:
        raise HTTPException(404, "Tenant not found (використовуйте підписаний маршрут)")
    return _store(db, tenant.id, provider, _external_id(body, raw), body)


@router.post("/{provider}/{integration_id}")
@limiter.limit("60/minute")
async def ingest_signed(provider: str, integration_id: str,
                        request: Request, db: Session = Depends(get_db)):
    """Підписаний маршрут: секрет або HMAC. Невірно → 404/401 без подробиць."""
    from uuid import UUID

    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(413, "Тіло завелике")
    try:
        row = db.query(Integration).filter(Integration.id == UUID(integration_id)).first()
    except Exception:
        row = None
    if not row or not row.is_active:
        raise HTTPException(404, "Not found")
    try:
        secret = (decrypt_credentials({"enc": row.webhook_secret})["v"]
                  if row.webhook_secret else "")
    except Exception:
        secret = ""
    if not secret:
        raise HTTPException(404, "Not found")
    given_secret = request.headers.get("X-Webhook-Secret") or request.query_params.get("secret")
    sig = request.headers.get("X-Signature")
    ok = False
    if given_secret:
        import hmac as _hmac
        ok = _hmac.compare_digest(given_secret, secret)
    elif sig:
        ok = verify_signature(secret, raw, sig)
    if not ok:
        raise HTTPException(401, "Bad signature")
    try:
        import json
        body = json.loads(raw) if raw else {}
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {"raw": str(body)[:2000]}
    return _store(db, row.tenant_id, provider, _external_id(body, raw), body)


@router.get("/pending")
def pending(user: User = Depends(_owner_admin),
            db: Session = Depends(get_db)):
    """Тільки свій тенант (фаза 1.1). Воркер читає БД напряму."""
    from datetime import datetime, timezone
    return db.query(WebhookEvent).filter(
        WebhookEvent.tenant_id == user.tenant_id,
        WebhookEvent.status.in_(["received", "failed"]),
        WebhookEvent.next_retry_at <= datetime.now(timezone.utc),
    ).order_by(WebhookEvent.next_retry_at).limit(50).all()
