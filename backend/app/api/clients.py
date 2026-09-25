"""CRUD с обязательным фильтром tenant_id + audit_log."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_tenant, get_current_user
from app.db.session import get_db
from app.models import AuditLog, Client, User
from app.schemas import ClientIn

router = APIRouter(prefix="/clients", tags=["clients"])


def _audit(db: Session, user: User, entity_id: str, action: str,
           old=None, new=None, request: Request | None = None):
    db.add(AuditLog(
        tenant_id=user.tenant_id, actor_id=user.id,
        entity_type="client", entity_id=entity_id, action=action,
        old_values=old, new_values=new,
        ip=request.client.host if request else None,
    ))


@router.get("")
def list_clients(tenant_id: UUID = Depends(get_current_tenant),
                 db: Session = Depends(get_db)):
    return db.query(Client).filter(
        Client.tenant_id == tenant_id, Client.deleted_at.is_(None)
    ).order_by(Client.created_at.desc()).limit(100).all()


@router.post("")
def create_client(data: ClientIn, request: Request,
                  user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    c = Client(tenant_id=user.tenant_id, **data.model_dump())
    db.add(c)
    db.flush()
    _audit(db, user, str(c.id), "create", new=data.model_dump(mode="json"), request=request)
    db.flush()
    # Тригер new_lead -> assign_manager / notify
    from app.services.automation import run_automations
    run_automations(db, user.tenant_id, "new_lead", {
        "client_id": str(c.id), "source": c.source,
        "manager_id": str(c.assigned_to) if c.assigned_to else None,
    })
    db.refresh(c)
    return c


@router.delete("/{client_id}")
def delete_client(client_id: UUID, request: Request,
                  user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    c = db.query(Client).filter(
        Client.id == client_id, Client.tenant_id == user.tenant_id
    ).first()
    if not c:
        raise HTTPException(404, "Not found")
    c.deleted_at = datetime.now(timezone.utc)  # soft-delete
    _audit(db, user, str(c.id), "delete", request=request)
    db.commit()
    return {"ok": True}
