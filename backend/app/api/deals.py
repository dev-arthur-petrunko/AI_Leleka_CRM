from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_tenant, get_current_user
from app.db.session import get_db
from app.models import Deal, User
from app.schemas import DealIn

router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("")
def list_deals(tenant_id: UUID = Depends(get_current_tenant),
               db: Session = Depends(get_db)):
    return db.query(Deal).filter(Deal.tenant_id == tenant_id)\
        .order_by(Deal.created_at.desc()).limit(100).all()


@router.post("")
def create_deal(data: DealIn, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    d = Deal(tenant_id=user.tenant_id, **data.model_dump())
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


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
               user: User = Depends(get_current_user),
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
