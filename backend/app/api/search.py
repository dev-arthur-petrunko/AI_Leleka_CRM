"""Глобальний пошук і «Сьогодні» (UI-3, UI-4): строго tenant_id."""

from datetime import datetime, timedelta, UTC
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_tenant, get_current_user
from app.core.phones import normalize_phone
from app.db.session import get_db
from app.models import Client, Conversation, Deal, Order, Task, User

router = APIRouter(tags=["search"])
_writer = get_current_user


@router.get("/search")
def search(q: str = Query(..., min_length=2),
           tenant_id: UUID = Depends(get_current_tenant),
           user: User = Depends(_writer),
           db: Session = Depends(get_db)):
    """По клієнтах (імʼя, нормалізований телефон), замовленнях (номер, ТТН), угодах."""
    like = f"%{q}%"
    clients = db.query(Client).filter(
        Client.tenant_id == tenant_id, Client.deleted_at.is_(None),
        (Client.name.ilike(like)) | (Client.phone.ilike(f"%{normalize_phone(q) or q}%"))) \
        .limit(5).all()
    deals = db.query(Deal).filter(
        Deal.tenant_id == tenant_id, Deal.title.ilike(like)).limit(5).all()
    orders = db.query(Order).filter(
        Order.tenant_id == tenant_id,
        (Order.order_number.ilike(like)) | (Order.external_id.ilike(like))).limit(5).all()
    return {
        "clients": [{"id": str(c.id), "name": c.name, "phone": c.phone} for c in clients],
        "deals": [{"id": str(d.id), "title": d.title, "stage": d.stage} for d in deals],
        "orders": [{"id": str(o.id), "number": o.order_number or o.external_id,
                    "status": o.status} for o in orders],
    }


@router.get("/today")
def today(tenant_id: UUID = Depends(get_current_tenant),
          user: User = Depends(_writer),
          db: Session = Depends(get_db)):
    """«Що зробити зараз»: прострочені задачі, завислі угоди, нові/неоплачені замовлення,
    непрочитані діалоги. Кожен рядок веде на обʼєкт."""
    now = datetime.now(UTC)
    items: list[dict] = []
    overdue = db.query(Task).filter(
        Task.tenant_id == tenant_id, Task.status == "open",
        Task.due_at.isnot(None), Task.due_at < now).limit(10).all()
    for t in overdue:
        items.append({"kind": "task_overdue", "title": t.title,
                      "ref": {"type": "task", "id": str(t.id)}})
    stuck = db.query(Deal).filter(
        Deal.tenant_id == tenant_id, Deal.stage.notin_(["won", "lost"]),
        Deal.last_activity_at < now - timedelta(days=3)).limit(10).all()
    for d in stuck:
        items.append({"kind": "deal_stuck", "title": d.title,
                      "ref": {"type": "deal", "id": str(d.id)}})
    fresh = db.query(Order).filter(
        Order.tenant_id == tenant_id,
        Order.status.in_(["new", "confirmed"])).limit(10).all()
    for o in fresh:
        items.append({"kind": "order_new",
                      "title": f"Замовлення {o.order_number or o.external_id}",
                      "ref": {"type": "order", "id": str(o.id)}})
    unread = db.query(Conversation).filter(
        Conversation.tenant_id == tenant_id,
        Conversation.status == "open").limit(10).all()
    for c in unread:
        items.append({"kind": "chat_unread", "title": f"Діалог ({c.channel})",
                      "ref": {"type": "conversation", "id": str(c.id)}})
    return {"date": now.date().isoformat(), "items": items, "count": len(items)}
