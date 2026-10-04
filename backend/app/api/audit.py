"""Журнал змін: читання audit_log (пишуть clients/billing)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_tenant
from app.db.session import get_db
from app.models import AuditLog, User

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit(tenant_id: UUID = Depends(get_current_tenant),
               db: Session = Depends(get_db),
               limit: int = Query(100, le=200)):
    rows = db.query(AuditLog, User.email).outerjoin(
        User, User.id == AuditLog.actor_id).filter(
        AuditLog.tenant_id == tenant_id).order_by(
        AuditLog.created_at.desc()).limit(limit).all()
    return [{"actor": email, "entity_type": r.entity_type,
             "entity_id": r.entity_id, "action": r.action,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r, email in rows]
