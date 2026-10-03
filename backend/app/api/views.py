"""Збережені види списків (UI-5)."""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_tenant, get_current_user
from app.db.session import get_db
from app.models import SavedView, User

router = APIRouter(prefix="/views", tags=["views"])


class ViewIn(BaseModel):
    entity: str  # deals/orders/clients
    name: str
    filters: dict = {}


@router.get("")
def list_views(entity: str, tenant_id: UUID = Depends(get_current_tenant),
               user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    return db.query(SavedView).filter(
        SavedView.tenant_id == tenant_id, SavedView.entity == entity,
        ((SavedView.user_id == user.id) | (SavedView.user_id.is_(None)))).all()


@router.post("")
def save_view(data: ViewIn, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    if data.entity not in ("deals", "orders", "clients"):
        from fastapi import HTTPException
        raise HTTPException(400, "entity: deals/orders/clients")
    row = SavedView(tenant_id=user.tenant_id, user_id=user.id,
                    entity=data.entity, name=data.name, filters=data.filters)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
