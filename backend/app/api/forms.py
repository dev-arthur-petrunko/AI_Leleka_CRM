"""Публічні форми заявок з сайту (фаза 3.8): секрет форми + honeypot + rate-limit."""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.core.rate import limiter
from app.db.session import get_db
from app.models import LeadForm, User
from app.services.orders import find_or_create_client, upsert_order

public_router = APIRouter(prefix="/api/v1/forms", tags=["forms"])
admin_router = APIRouter(prefix="/forms", tags=["forms"])
_admin = require_role("owner", "admin")


class FormIn(BaseModel):
    name: str


class LeadIn(BaseModel):
    secret: str
    name: str = ""
    phone: str | None = None
    email: str | None = None
    comment: str = ""
    website: str = ""  # honeypot: люди лишають порожнім, боти заповнюють


@admin_router.post("")
def create_form(data: FormIn, user: User = Depends(_admin),
                db: Session = Depends(get_db)):
    row = LeadForm(tenant_id=user.tenant_id, name=data.name,
                   secret=secrets.token_urlsafe(24))
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": str(row.id), "secret": row.secret,
            "post_url": f"/api/v1/forms/{row.id}"}


@public_router.post("/{form_id}")
@limiter.limit("30/minute")
def submit_lead(form_id: str, data: LeadIn, request: Request,
                db: Session = Depends(get_db)):
    from uuid import UUID

    try:
        form = db.query(LeadForm).filter(
            LeadForm.id == UUID(form_id),
            LeadForm.secret == data.secret,
            LeadForm.is_active.is_(True)).first()
    except Exception:
        form = None
    if not form:
        raise HTTPException(404, "Not found")
    if data.website:
        return {"ok": True}  # honeypot: тиха відмова спаму
    client = find_or_create_client(db, form.tenant_id, data.name or "Лід з сайту",
                                   data.phone, data.email, source="site")
    upsert_order(db, form.tenant_id, {
        "source": "site", "external_id": f"form-{form_id}-{client.id}",
        "client_name": data.name, "phone": data.phone, "email": data.email,
        "total": 0, "raw": {"comment": data.comment}}, origin="form")
    return {"ok": True}
