from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.deps import get_current_tenant
from app.services import notify

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def inbox(tenant_id: UUID = Depends(get_current_tenant)):
    """Останні сповіщення менеджера (Redis-інбокс, не губиться серед задач)."""
    return notify.pull(tenant_id)
