from uuid import UUID

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
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


class TaskPatch(BaseModel):
    title: str | None = None
    status: str | None = None  # open/done/cancelled
    priority: str | None = None  # high/normal/low
    due_at: datetime | None = None


@router.patch("/{task_id}")
def update_task(task_id: UUID, data: TaskPatch, user=Depends(_writer),
                db: Session = Depends(get_db)):
    t = db.query(Task).filter(
        Task.id == task_id, Task.tenant_id == user.tenant_id).first()
    if not t:
        raise HTTPException(404, "Not found")
    if data.status is not None:
        if data.status not in ("open", "done", "cancelled"):
            raise HTTPException(400, "status: open/done/cancelled")
        t.status = data.status
        t.completed_at = datetime.now(UTC) if data.status == "done" else None
    if data.title is not None:
        t.title = data.title
    if data.priority is not None:
        if data.priority not in ("high", "normal", "low"):
            raise HTTPException(400, "priority: high/normal/low")
        t.priority = data.priority
    if data.due_at is not None:
        t.due_at = data.due_at
    db.commit()
    db.refresh(t)
    return t


@router.delete("/{task_id}")
def delete_task(task_id: UUID, user=Depends(_writer),
                db: Session = Depends(get_db)):
    t = db.query(Task).filter(
        Task.id == task_id, Task.tenant_id == user.tenant_id).first()
    if not t:
        raise HTTPException(404, "Not found")
    db.delete(t)
    db.commit()
    return {"ok": True}
