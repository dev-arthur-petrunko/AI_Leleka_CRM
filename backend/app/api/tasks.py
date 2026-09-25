from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_tenant, get_current_user
from app.db.session import get_db
from app.models import Task, User
from app.schemas import TaskIn

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
def list_tasks(tenant_id: UUID = Depends(get_current_tenant),
               db: Session = Depends(get_db)):
    return db.query(Task).filter(Task.tenant_id == tenant_id)\
        .order_by(Task.due_at.asc().nullslast()).limit(100).all()


@router.post("")
def create_task(data: TaskIn, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    t = Task(tenant_id=user.tenant_id, **data.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    return t
