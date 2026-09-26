import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.core.deps import get_current_tenant, require_role
from app.db.session import get_db
from app.models import Deal
from app.schemas import DealIn

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
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return db.query(Deal).filter(
        Deal.tenant_id == tenant_id,
        Deal.stage.notin_(["won", "lost"]),
        Deal.last_activity_at < cutoff,
    ).all()


@router.patch("/{deal_id}/stage")
def move_stage(deal_id: UUID, stage: str,
               user=Depends(_writer),
               db: Session = Depends(get_db)):
    d = db.query(Deal).filter(
        Deal.id == deal_id, Deal.tenant_id == user.tenant_id
    ).first()
    if not d:
        raise HTTPException(404, "Not found")
    d.stage = stage
    from datetime import datetime, timezone
    d.last_activity_at = datetime.now(timezone.utc)
    if stage == "won":
        d.won_at = datetime.now(timezone.utc)
    if stage == "lost":
        d.lost_at = datetime.now(timezone.utc)
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
