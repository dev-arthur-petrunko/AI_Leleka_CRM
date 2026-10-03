"""Ідемпотентний імпорт замовлень (фаза 2.3): єдина точка входу для вебхуків,
polling і ручного створення. Повтор = той самий результат (ON CONFLICT)."""

from datetime import datetime, UTC
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.phones import normalize_phone
from app.models import Client, Deal, Order, OrderItem, OrderStatusHistory


def find_or_create_client(db: Session, tenant_id: UUID, name: str,
                          phone: str | None = None, email: str | None = None,
                          source: str = "manual") -> Client:
    norm = normalize_phone(phone)
    client = None
    if norm:
        client = db.query(Client).filter(
            Client.tenant_id == tenant_id, Client.phone == norm,
            Client.deleted_at.is_(None)).first()
    if not client and email:
        client = db.query(Client).filter(
            Client.tenant_id == tenant_id, Client.email == email,
            Client.deleted_at.is_(None)).first()
    if not client:
        client = Client(tenant_id=tenant_id, name=name or "Без імені",
                        phone=norm, email=email, source=source)
        db.add(client)
        db.flush()
    return client


def upsert_order(db: Session, tenant_id: UUID, dto: dict,
                 origin: str = "manager") -> Order:
    """dto: source, external_id, client_name/phone/email, status, items[{sku,name,qty,unit_price}],
    total, currency, payment_*, order_number, placed_at, raw."""
    now = datetime.now(UTC)
    items = dto.pop("items", [])
    client = find_or_create_client(db, tenant_id, dto.get("client_name", ""),
                                   dto.get("phone"), dto.get("email"),
                                   dto.get("source", "manual"))
    stmt = insert(Order).values(
        tenant_id=tenant_id, client_id=client.id,
        source=dto.get("source", "manual"), external_id=dto["external_id"],
        order_number=dto.get("order_number"), status=dto.get("status", "new"),
        payment_status=dto.get("payment_status", "unpaid"),
        payment_method=dto.get("payment_method"),
        currency=dto.get("currency", "UAH"),
        subtotal=dto.get("subtotal", dto.get("total", 0)),
        discount=dto.get("discount", 0),
        shipping_cost=dto.get("shipping_cost", 0),
        total=dto.get("total", 0),
        placed_at=dto.get("placed_at"), raw=dto.get("raw") or {},
        created_at=now, updated_at=now,
    ).on_conflict_do_update(
        index_elements=["tenant_id", "source", "external_id"],
        set_={"status": dto.get("status", "new"),
              "payment_status": dto.get("payment_status", "unpaid"),
              "total": dto.get("total", 0), "updated_at": now,
              "raw": dto.get("raw") or {}},
    ).returning(Order.id)
    order_id = db.execute(stmt).scalar_one()
    order = db.query(Order).filter(Order.id == order_id).first()
    # позиції — повна пересинхронізація
    db.query(OrderItem).filter(OrderItem.order_id == order.id).delete()
    for it in items:
        qty = float(it.get("qty", 1) or 1)
        price = float(it.get("unit_price", 0) or 0)
        db.add(OrderItem(tenant_id=tenant_id, order_id=order.id,
                         product_id=it.get("product_id"), sku=it.get("sku"),
                         name=it.get("name", ""), qty=qty, unit_price=price,
                         discount=float(it.get("discount", 0) or 0),
                         total=qty * price))
    # історія + автоматизації при зміні статусу
    last = db.query(OrderStatusHistory).filter(
        OrderStatusHistory.order_id == order.id)\
        .order_by(OrderStatusHistory.changed_at.desc()).first()
    if not last or last.to_status != order.status:
        db.add(OrderStatusHistory(tenant_id=tenant_id, order_id=order.id,
                                  from_status=last.to_status if last else None,
                                  to_status=order.status, changed_at=now,
                                  source=origin))
        _fire_order_automations(db, tenant_id, order, origin)
    # повʼязана угода для канбана
    if not order.deal_id:
        deal = Deal(tenant_id=tenant_id, client_id=client.id,
                    title=f"Замовлення {order.order_number or order.external_id}",
                    amount=order.total, stage="new",
                    last_activity_at=now)
        db.add(deal)
        db.flush()
        order.deal_id = deal.id
    db.commit()
    db.refresh(order)
    return order


def _fire_order_automations(db: Session, tenant_id: UUID, order: Order, origin: str):
    from app.services.automation import run_automations

    mapping = {"paid": "order_paid", "shipped": "order_shipped",
               "delivered": "order_delivered", "returned": "order_returned"}
    trigger = {"new": "order_created"}.get(order.status) or mapping.get(order.payment_status) \
        or mapping.get(order.status) or "order_status_changed"
    run_automations(db, tenant_id, trigger, {
        "order_id": str(order.id), "client_id": str(order.client_id),
        "deal_id": str(order.deal_id) if order.deal_id else None,
        "stage": order.status, "amount": float(order.total or 0),
        "source": order.source, "origin": origin,
    })
