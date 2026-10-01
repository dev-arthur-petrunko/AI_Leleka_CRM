"""API замовлень + теги/кастом/воронки (фаза 2.4–2.5)."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_tenant, require_role
from app.db.session import get_db
from app.models import (
    CustomFieldDef,
    EntityTag,
    Order,
    OrderItem,
    OrderStatusHistory,
    Payment,
    Pipeline,
    PipelineStage,
    Return,
    Shipment,
    Tag,
    User,
)
from app.services.orders import upsert_order

_writer = require_role("owner", "admin", "manager")

router = APIRouter(prefix="/orders", tags=["orders"])

LEGACY_STAGES = [("new", "Нові"), ("contacted", "Контакт"), ("negotiation", "Переговори"),
                 ("won", "Виграно"), ("lost", "Втрачено")]


class OrderItemIn(BaseModel):
    sku: str | None = None
    name: str = ""
    qty: float = 1
    unit_price: float = 0


class OrderIn(BaseModel):
    source: str = "manual"
    external_id: str
    client_name: str = ""
    phone: str | None = None
    email: str | None = None
    status: str = "new"
    payment_status: str = "unpaid"
    total: float = 0
    currency: str = "UAH"
    order_number: str | None = None
    items: list[OrderItemIn] = []


@router.get("")
def list_orders(tenant_id: UUID = Depends(get_current_tenant),
                db: Session = Depends(get_db),
                status: str | None = Query(None), source: str | None = Query(None),
                payment_status: str | None = Query(None),
                q: str | None = Query(None),
                limit: int = Query(50, le=200), offset: int = Query(0, ge=0)):
    query = db.query(Order).filter(Order.tenant_id == tenant_id)
    if status:
        query = query.filter(Order.status == status)
    if source:
        query = query.filter(Order.source == source)
    if payment_status:
        query = query.filter(Order.payment_status == payment_status)
    if q:
        like = f"%{q}%"
        query = query.filter((Order.order_number.ilike(like))
                             | (Order.external_id.ilike(like)))
    total = query.count()
    return {"total": total, "limit": limit, "offset": offset,
            "items": query.order_by(Order.created_at.desc()).limit(limit).offset(offset).all()}


@router.post("")
def create_order(data: OrderIn, user: User = Depends(_writer),
                 db: Session = Depends(get_db)):
    return upsert_order(db, user.tenant_id, data.model_dump(), origin="manager")


@router.post("/import-csv")
def import_orders_csv(file: UploadFile = File(...), mapping: str = "{}",
                      user: User = Depends(_writer),
                      db: Session = Depends(get_db)):
    """Імпорт замовлень з CSV з маппингом колонок (фаза 3.8).
    mapping: JSON {"col_name": "field"}, field ∈ external_id, client_name,
    phone, email, total, order_number, status."""
    import csv
    import io
    import json

    try:
        field_map = json.loads(mapping or "{}")
    except Exception:
        raise HTTPException(400, "mapping — невалідний JSON")
    raw = file.file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "Файл завеликий (>5 МБ)")
    from app.services.orders import upsert_order

    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    n = 0
    for i, row in enumerate(reader):
        get = lambda f, default="": (row.get(field_map.get(f, f)) or default).strip()
        if not get("external_id") and not get("client_name"):
            continue
        try:
            total = float(get("total") or 0)
        except ValueError:
            total = 0
        upsert_order(db, user.tenant_id, {
            "source": "manual", "external_id": get("external_id") or f"csv-{i}",
            "client_name": get("client_name"), "phone": get("phone"),
            "email": get("email"), "total": total,
            "order_number": get("order_number"),
            "status": get("status") or "new"}, origin="csv")
        n += 1
        if n >= 2000:
            break
    return {"ok": True, "imported": n}


@router.get("/{order_id:uuid}")
def get_order(order_id: UUID, tenant_id: UUID = Depends(get_current_tenant),
              db: Session = Depends(get_db)):
    order = db.query(Order).filter(
        Order.id == order_id, Order.tenant_id == tenant_id).first()
    if not order:
        raise HTTPException(404, "Not found")
    return {"order": order,
            "items": db.query(OrderItem).filter(OrderItem.order_id == order.id).all(),
            "payments": db.query(Payment).filter(Payment.order_id == order.id).all(),
            "shipments": db.query(Shipment).filter(Shipment.order_id == order.id).all(),
            "history": db.query(OrderStatusHistory).filter(
                OrderStatusHistory.order_id == order.id)
            .order_by(OrderStatusHistory.changed_at).all()}


class StatusIn(BaseModel):
    status: str


@router.patch("/{order_id:uuid}/status")
def set_status(order_id: UUID, data: StatusIn, user: User = Depends(_writer),
               db: Session = Depends(get_db)):
    order = db.query(Order).filter(
        Order.id == order_id, Order.tenant_id == user.tenant_id).first()
    if not order:
        raise HTTPException(404, "Not found")
    order.status = data.status
    order.updated_at = datetime.now()
    db.commit()
    from app.services.orders import _fire_order_automations
    _fire_order_automations(db, user.tenant_id, order, origin="manager")
    db.refresh(order)
    return order


class ShipmentIn(BaseModel):
    carrier: str = "novaposhta"
    cod_amount: float = 0


@router.post("/{order_id:uuid}/shipments")
def create_shipment(order_id: UUID, data: ShipmentIn,
                    user: User = Depends(_writer), db: Session = Depends(get_db)):
    """Створити ТТН через адаптер перевізника (реальний виклик, не stub)."""
    order = db.query(Order).filter(
        Order.id == order_id, Order.tenant_id == user.tenant_id).first()
    if not order:
        raise HTTPException(404, "Not found")
    if data.carrier != "novaposhta":
        raise HTTPException(400, "Поки тільки novaposhta")
    from app.core.security import decrypt_credentials
    from app.integrations.novaposhta import NovaPoshtaAdapter
    from app.models import Client, Integration

    row = db.query(Integration).filter(
        Integration.tenant_id == user.tenant_id,
        Integration.provider == "novaposhta").first()
    if not row:
        raise HTTPException(404, "Підключіть Нову Пошту")
    client = db.query(Client).filter(Client.id == order.client_id).first()
    resp = NovaPoshtaAdapter(decrypt_credentials(row.credentials),
                             row.settings).create_ttn(
        recipient_phone=(client.phone or "") if client else "",
        recipient_city=(row.settings or {}).get("city_recipient", "Київ"),
        cod=data.cod_amount or float(order.total or 0))
    if not resp.get("ok"):
        raise HTTPException(502, f"НП: {resp.get('error')}")
    ttn = None
    try:
        ttn = (resp.get("data") or {}).get("data", [{}])[0].get("IntDocNumber")
    except Exception:
        ttn = None
    ship = Shipment(tenant_id=user.tenant_id, order_id=order.id,
                    carrier="novaposhta", ttn=ttn or ("STUB" if resp.get("stub") else None),
                    cod_amount=data.cod_amount)
    db.add(ship)
    db.commit()
    db.refresh(ship)
    return ship


class ReturnIn(BaseModel):
    reason: str = ""
    amount: float = 0


@router.post("/{order_id:uuid}/returns")
def create_return(order_id: UUID, data: ReturnIn, user: User = Depends(_writer),
                  db: Session = Depends(get_db)):
    order = db.query(Order).filter(
        Order.id == order_id, Order.tenant_id == user.tenant_id).first()
    if not order:
        raise HTTPException(404, "Not found")
    ret = Return(tenant_id=user.tenant_id, order_id=order.id,
                 reason=data.reason, amount=data.amount)
    db.add(ret)
    db.commit()
    db.refresh(ret)
    return ret


# ---------- теги / кастом / воронки ----------

class TagIn(BaseModel):
    name: str
    color: str | None = None
    entity_type: str = "client"
    entity_id: str = ""


tags_router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("/export")
def export_orders(tenant_id: UUID = Depends(get_current_tenant),
                  db: Session = Depends(get_db)):
    """Експорт замовлень у CSV (фаза 6.4)."""
    import csv
    import io

    from starlette.responses import StreamingResponse

    rows = db.query(Order).filter(Order.tenant_id == tenant_id).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "source", "external_id", "order_number", "status",
                "payment_status", "total", "currency", "client_id", "placed_at"])
    for o in rows:
        w.writerow([o.id, o.source, o.external_id, o.order_number or "",
                    o.status, o.payment_status, float(o.total or 0),
                    o.currency, o.client_id or "", o.placed_at or ""])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=orders.csv"})


@router.get("/tags/all")
def list_tags(tenant_id: UUID = Depends(get_current_tenant),
              db: Session = Depends(get_db)):
    return db.query(Tag).filter(Tag.tenant_id == tenant_id).all()


@router.post("/tags/attach")
def attach_tag(data: TagIn, user: User = Depends(_writer),
               db: Session = Depends(get_db)):
    tag = db.query(Tag).filter(Tag.tenant_id == user.tenant_id,
                               Tag.name == data.name).first()
    if not tag:
        tag = Tag(tenant_id=user.tenant_id, name=data.name, color=data.color)
        db.add(tag)
        db.flush()
    exists = db.query(EntityTag).filter(
        EntityTag.tenant_id == user.tenant_id, EntityTag.tag_id == tag.id,
        EntityTag.entity_type == data.entity_type,
        EntityTag.entity_id == data.entity_id).first()
    if not exists:
        db.add(EntityTag(tenant_id=user.tenant_id, tag_id=tag.id,
                         entity_type=data.entity_type, entity_id=data.entity_id))
    db.commit()
    return {"ok": True, "tag_id": str(tag.id)}


class CustomDefIn(BaseModel):
    entity: str
    key: str
    label: str
    ftype: str = "text"


@router.get("/custom-fields")
def list_custom(tenant_id: UUID = Depends(get_current_tenant),
                db: Session = Depends(get_db)):
    return db.query(CustomFieldDef).filter(
        CustomFieldDef.tenant_id == tenant_id).all()


@router.post("/custom-fields")
def add_custom(data: CustomDefIn, user: User = Depends(_writer),
               db: Session = Depends(get_db)):
    if data.entity not in ("client", "order") or data.ftype not in ("text", "number", "date", "bool"):
        raise HTTPException(400, "entity: client/order; ftype: text/number/date/bool")
    row = CustomFieldDef(tenant_id=user.tenant_id, **data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/pipelines")
def list_pipelines(tenant_id: UUID = Depends(get_current_tenant),
                   db: Session = Depends(get_db)):
    out = []
    for p in db.query(Pipeline).filter(Pipeline.tenant_id == tenant_id).all():
        stages = db.query(PipelineStage).filter(
            PipelineStage.pipeline_id == p.id).order_by(PipelineStage.position).all()
        out.append({"pipeline": p, "stages": stages})
    if not out:
        out = [{"pipeline": {"name": "Продажі (default)"},
                "stages": [{"key": k, "name": n} for k, n in
                           [("new", "Нові"), ("contacted", "Контакт"),
                            ("negotiation", "Переговори"), ("won", "Виграно"),
                            ("lost", "Втрачено")]]}]
    return out
