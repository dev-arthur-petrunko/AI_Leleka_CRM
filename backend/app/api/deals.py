import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.core.deps import get_current_tenant, require_role
from app.db.session import get_db
from app.models import Deal
from app.schemas import DealIn
from datetime import UTC

_writer = require_role("owner", "admin", "manager")

router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("")
def list_deals(tenant_id: UUID = Depends(get_current_tenant),
               db: Session = Depends(get_db),
               stage: str | None = Query(None, description="new/contacted/negotiation/won/lost"),
               manager_id: UUID | None = Query(None),
               limit: int = Query(50, le=200), offset: int = Query(0, ge=0)):
    q = db.query(Deal).filter(Deal.tenant_id == tenant_id)
    if stage:
        q = q.filter(Deal.stage == stage)
    if manager_id:
        q = q.filter(Deal.manager_id == manager_id)
    total = q.count()
    rows = q.order_by(Deal.created_at.desc()).limit(limit).offset(offset).all()
    return {"total": total, "limit": limit, "offset": offset, "items": rows}


@router.post("")
def create_deal(data: DealIn, user=Depends(_writer),
                db: Session = Depends(get_db)):
    d = Deal(tenant_id=user.tenant_id, **data.model_dump())
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


class DealPatch(BaseModel):
    title: str | None = None
    amount: float | None = None
    client_id: UUID | None = None
    manager_id: UUID | None = None
    probability: int | None = None


@router.patch("/{deal_id}")
def update_deal(deal_id: UUID, data: DealPatch, user=Depends(_writer),
                db: Session = Depends(get_db)):
    from app.models import Client, User

    d = db.query(Deal).filter(
        Deal.id == deal_id, Deal.tenant_id == user.tenant_id).first()
    if not d:
        raise HTTPException(404, "Not found")
    if data.title is not None:
        if not data.title.strip():
            raise HTTPException(400, "title порожній")
        d.title = data.title.strip()
    if data.amount is not None:
        if data.amount < 0:
            raise HTTPException(400, "amount >= 0")
        d.amount = data.amount
    if data.client_id is not None:
        c = db.query(Client).filter(
            Client.id == data.client_id,
            Client.tenant_id == user.tenant_id).first()
        if not c:
            raise HTTPException(400, "Клієнта не знайдено у вашій компанії")
        d.client_id = data.client_id
    if data.manager_id is not None:
        m = db.query(User).filter(
            User.id == data.manager_id,
            User.tenant_id == user.tenant_id).first()
        if not m:
            raise HTTPException(400, "Менеджера не знайдено у вашій компанії")
        d.manager_id = data.manager_id
    if data.probability is not None:
        if not 0 <= data.probability <= 100:
            raise HTTPException(400, "probability 0..100")
        d.probability = data.probability
    from datetime import datetime
    d.last_activity_at = datetime.now(UTC)
    db.commit()
    db.refresh(d)
    return d


@router.get("/export")
def export_csv(tenant_id: UUID = Depends(get_current_tenant),
               db: Session = Depends(get_db)):
    """Експорт угод у CSV для бухгалтера (прод — PDF-звіт)."""
    rows = db.query(Deal).filter(Deal.tenant_id == tenant_id).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "title", "amount", "currency", "stage", "loss_reason",
                "client_id", "manager_id", "created_at"])
    for d in rows:
        w.writerow([d.id, d.title, float(d.amount or 0), d.currency, d.stage,
                    d.loss_reason or "", d.client_id, d.manager_id or "", d.created_at])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=deals.csv"})


@router.get("/stuck")
def stuck_deals(days: int = 3,
                tenant_id: UUID = Depends(get_current_tenant),
                db: Session = Depends(get_db)):
    """Угоди без руху N днів — для тригера deal_stuck."""
    from datetime import datetime, timedelta
    cutoff = datetime.now(UTC) - timedelta(days=days)
    return db.query(Deal).filter(
        Deal.tenant_id == tenant_id,
        Deal.stage.notin_(["won", "lost"]),
        Deal.last_activity_at < cutoff,
    ).all()


@router.patch("/{deal_id}/stage")
def move_stage(deal_id: UUID, stage: str, loss_reason: str | None = None,
               user=Depends(_writer),
               db: Session = Depends(get_db)):
    if stage == "lost" and not (loss_reason or "").strip():
        raise HTTPException(400, "Причина програшу обовʼязкова (UI-5)")
    d = db.query(Deal).filter(
        Deal.id == deal_id, Deal.tenant_id == user.tenant_id
    ).first()
    if not d:
        raise HTTPException(404, "Not found")
    d.stage = stage
    # фаза 6.3: ймовірність синхронізується зі стадією воронки
    d.probability = {"new": 10, "contacted": 30, "negotiation": 60,
                     "won": 100, "lost": 0}.get(stage, d.probability or 0)
    from datetime import datetime
    d.last_activity_at = datetime.now(UTC)
    if stage == "won":
        d.won_at = datetime.now(UTC)
    if stage == "lost":
        d.lost_at = datetime.now(UTC)
        d.loss_reason = loss_reason
    db.flush()
    # Тригеры deal_won / deal_lost
    from app.services.automation import run_automations
    if stage in ("won", "lost"):
        run_automations(db, user.tenant_id, f"deal_{stage}", {
            "deal_id": str(d.id), "client_id": str(d.client_id),
            "manager_id": str(d.manager_id) if d.manager_id else None,
            "stage": stage, "amount": float(d.amount or 0),
        })
    else:
        db.commit()
    return d


class ConvertIn(BaseModel):
    total: float = 0
    shipping_cost: float = 0


@router.post("/{deal_id}/convert-to-order")
def convert_to_order(deal_id: UUID, data: ConvertIn,
                     user=Depends(_writer),
                     db: Session = Depends(get_db)):
    """Виграна угода → замовлення. Ідемпотентно: повтор повертає те саме."""
    from app.models import Client, Order

    d = db.query(Deal).filter(
        Deal.id == deal_id, Deal.tenant_id == user.tenant_id
    ).first()
    if not d:
        raise HTTPException(404, "Not found")
    if d.converted_order_id:
        order = db.query(Order).filter(Order.id == d.converted_order_id).first()
        return {"order_id": str(order.id), "deduplicated": True}
    client = db.query(Client).filter(Client.id == d.client_id).first()
    if not client:
        raise HTTPException(404, "Клієнта угоди не знайдено")
    order = Order(tenant_id=user.tenant_id, client_id=d.client_id,
                  deal_id=d.id, source="manual",
                  external_id=f"deal-{d.id}",
                  order_number=f"D-{str(d.id)[:8]}",
                  status="confirmed", total=data.total or float(d.amount or 0),
                  shipping_cost=data.shipping_cost)
    db.add(order)
    db.flush()
    d.converted_order_id = order.id
    d.stage = "won"
    db.commit()
    return {"order_id": str(order.id), "deduplicated": False}
