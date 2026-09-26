from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_tenant, require_role
from app.db.session import get_db
from app.models import Task
from app.schemas import TaskIn

_writer = require_role("owner", "admin", "manager")

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
def list_tasks(tenant_id: UUID = Depends(get_current_tenant),
               db: Session = Depends(get_db),
               status: str | None = Query(None, description="open/done/cancelled"),
               assignee_id: UUID | None = Query(None),
               limit: int = Query(50, le=200), offset: int = Query(0, ge=0)):
    q = db.query(Task).filter(Task.tenant_id == tenant_id)
    if status:
        q = q.filter(Task.status == status)
    if assignee_id:
        q = q.filter(Task.assignee_id == assignee_id)
    return q.order_by(Task.due_at.asc().nullslast()).limit(limit).offset(offset).all()


@router.post("")
def create_task(data: TaskIn, user=Depends(_writer),
                db: Session = Depends(get_db)):
    t = Task(tenant_id=user.tenant_id, **data.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    return t
