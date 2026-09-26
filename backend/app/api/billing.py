"""Білінг з реальною оплатою (діра «безкоштовний Team» закрита).

Флоу платного апгрейда:
1. owner → POST /billing/upgrade {new_plan, provider} → рахунок BillingOrder(pending)
   + інвойс LiqPay (data+signature) або Mono (pageUrl).
2. Клієнт платить на стороні провайдера.
3. Провайдер → POST /billing/webhook/liqpay|monobank → перевірка підпису/статусу
   → ТІЛЬКИ ТОДІ tenant.plan змінюється + audit.
Безкоштовний план / даунгрейд — одразу (грошей не треба).
Без PLATFORM_*-ключів платний апгрейд повертає 409, а не мовчазний Team.
"""

import base64
import hashlib
import hmac
import json
import time
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_tenant, get_current_user, require_role
from app.db.session import get_db
from app.integrations.payments import LiqPayAdapter, MonoAdapter
from app.models import AuditLog, BillingOrder, Tenant, User
from app.services.billing import PLANS, check_seats, current_plan

router = APIRouter(prefix="/billing", tags=["billing"])

_owner = require_role("owner")


class UpgradeIn(BaseModel):
    new_plan: str
    provider: str = "liqpay"  # liqpay | monobank


@router.get("/plans")
def plans():
    return PLANS


@router.get("/current")
def current(tenant_id: UUID = Depends(get_current_tenant),
            db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    seats_used = db.query(User).filter(
        User.tenant_id == tenant_id, User.is_active.is_(True)).count()
    plan = current_plan(tenant)
    return {"plan": tenant.plan, "label": plan["label"],
            "seats_used": seats_used, "seats_limit": plan["seats"],
            "features": plan["features"],
            "price_per_seat_uah": plan["price_uah"],
            "monthly_total_uah": plan["price_uah"] * max(seats_used, 1)}


@router.get("/orders")
def orders(user: User = Depends(_owner), db: Session = Depends(get_db)):
    return db.query(BillingOrder).filter(
        BillingOrder.tenant_id == user.tenant_id)\
        .order_by(BillingOrder.created_at.desc()).limit(50).all()


@router.post("/upgrade")
def upgrade(data: UpgradeIn, user: User = Depends(_owner),
            db: Session = Depends(get_db)):
    """ТІЛЬКИ owner. Платний план — лише через рахунок + paid-вебхук."""
    if data.new_plan not in PLANS:
        raise HTTPException(400, f"Unknown plan. Available: {list(PLANS)}")
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if tenant.plan == data.new_plan:
        return {"ok": True, "plan": tenant.plan, "message": "Тариф уже активний"}
    # Тарифи заявлені "за місце" (350/300 грн) — рахунок мусить множитись
    # на реальну кількість активних співробітників, а не бути фіксованим.
    seats_billed = max(1, db.query(User).filter(
        User.tenant_id == user.tenant_id, User.is_active.is_(True)).count())
    price = PLANS[data.new_plan]["price_uah"] * seats_billed
    if price == 0:
        _apply_plan(db, user, tenant, data.new_plan, order_id=None, seats_billed=seats_billed)
        return {"ok": True, "plan": data.new_plan, "payment_required": False}
    if data.provider not in ("liqpay", "monobank"):
        raise HTTPException(400, "provider must be liqpay or monobank")
    order_id = f"leleka-{str(tenant.id)[:8]}-{data.new_plan}-{int(time.time())}"
    if data.provider == "liqpay":
        if not (settings.PLATFORM_LIQPAY_PUBLIC_KEY and settings.PLATFORM_LIQPAY_PRIVATE_KEY):
            raise HTTPException(409, "Оплата LiqPay не налаштована власником сервісу")
        adapter = LiqPayAdapter(
            {"public_key": settings.PLATFORM_LIQPAY_PUBLIC_KEY,
             "private_key": settings.PLATFORM_LIQPAY_PRIVATE_KEY}, {})
        inv = adapter.invoice_link(price, order_id, f"AI Leleka CRM: {data.new_plan}")
        pay = {"data": inv["data"], "signature": inv["signature"]}
    else:
        if not settings.PLATFORM_MONO_TOKEN:
            raise HTTPException(409, "Оплата Monobank не налаштована власником сервісу")
        adapter = MonoAdapter({"token": settings.PLATFORM_MONO_TOKEN}, {})
        resp = adapter.create_invoice(price)
        if not resp.get("ok"):
            raise HTTPException(502, f"Mono: {resp.get('error')}")
        pay = resp["data"]
    db.add(BillingOrder(tenant_id=user.tenant_id, plan=data.new_plan,
                        provider=data.provider, order_id=order_id,
                        amount_uah=price, seats_billed=seats_billed, status="pending"))
    db.commit()
    return {"ok": True, "payment_required": True, "order_id": order_id,
            "amount_uah": price, "seats_billed": seats_billed, "pay": pay}


@router.post("/webhook/liqpay")
def webhook_liqpay(data: str = Form(...), signature: str = Form(...),
                   db: Session = Depends(get_db)):
    """Колбек LiqPay: перевірка підпису → paid → зміна плану."""
    if not settings.PLATFORM_LIQPAY_PRIVATE_KEY:
        raise HTTPException(409, "LiqPay не налаштовано")
    expect = base64.b64encode(hashlib.sha1(
        (settings.PLATFORM_LIQPAY_PRIVATE_KEY + data
         + settings.PLATFORM_LIQPAY_PRIVATE_KEY).encode()).digest()).decode()
    if not hmac.compare_digest(expect, signature):
        raise HTTPException(403, "Bad signature")
    payload = json.loads(base64.b64decode(data).decode())
    if payload.get("status") != "success":
        return {"ok": True, "status": payload.get("status"), "message": "Не оплачено"}
    return _confirm_paid(db, payload.get("order_id"))


@router.post("/webhook/monobank")
def webhook_monobank(body: dict, db: Session = Depends(get_db)):
    """Колбек Mono: статус перевіряємо сервер-сервер за invoiceId (не довіряємо тілу)."""
    if not settings.PLATFORM_MONO_TOKEN:
        raise HTTPException(409, "Monobank не налаштовано")
    invoice_id = body.get("invoiceId")
    if not invoice_id:
        raise HTTPException(400, "No invoiceId")
    import requests
    r = requests.get("https://api.monobank.ua/api/merchant/invoice/status",
                     params={"invoiceId": invoice_id},
                     headers={"X-Token": settings.PLATFORM_MONO_TOKEN}, timeout=15)
    r.raise_for_status()
    if r.json().get("status") != "success":
        return {"ok": True, "status": r.json().get("status"), "message": "Не оплачено"}
    order = db.query(BillingOrder).filter(
        BillingOrder.order_id == invoice_id,
        BillingOrder.provider == "monobank").first()
    if not order:
        raise HTTPException(404, "Order not found")
    return _confirm_paid(db, order.order_id)


def _confirm_paid(db: Session, order_id: str) -> dict:
    from datetime import datetime, timezone
    order = db.query(BillingOrder).filter(BillingOrder.order_id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    if order.status == "paid":
        return {"ok": True, "plan": order.plan, "message": "Уже оплачено"}
    tenant = db.query(Tenant).filter(Tenant.id == order.tenant_id).first()
    order.status = "paid"
    order.paid_at = datetime.now(timezone.utc)
    _apply_plan(db, None, tenant, order.plan, order_id=order_id, seats_billed=order.seats_billed)
    return {"ok": True, "plan": order.plan}


def _apply_plan(db: Session, user: User | None, tenant: Tenant,
                new_plan: str, order_id: str | None, seats_billed: int = 1):
    old = tenant.plan
    tenant.plan = new_plan
    db.add(AuditLog(tenant_id=tenant.id, actor_id=user.id if user else None,
                    entity_type="tenant", entity_id=str(tenant.id),
                    action="update", old_values={"plan": old},
                    new_values={"plan": new_plan, "order_id": order_id,
                                "seats_billed": seats_billed}))
    db.commit()


@router.post("/invite-check")
def invite_check(user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """Викликати ПЕРЕД створенням нового user — перевірка ліміту місць."""
    check_seats(db, user.tenant_id)
    return {"ok": True, "message": "Є вільне місце"}
