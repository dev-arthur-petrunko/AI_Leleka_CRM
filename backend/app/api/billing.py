from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_tenant, get_current_user, require_role
from app.db.session import get_db
from app.models import Tenant, User
from app.services.billing import PLANS, check_seats, current_plan

router = APIRouter(prefix="/billing", tags=["billing"])

_owner = require_role("owner")


@router.get("/plans")
def plans():
    return PLANS


@router.get("/current")
def current(tenant_id: UUID = Depends(get_current_tenant),
            db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    seats_used = db.query(User).filter(
        User.tenant_id == tenant_id, User.is_active.is_(True)).count()
    plan = current_plan(tenant)
    return {"plan": tenant.plan, "label": plan["label"],
            "seats_used": seats_used, "seats_limit": plan["seats"],
            "features": plan["features"]}


@router.post("/upgrade")
def upgrade(new_plan: str, user: User = Depends(_owner),
            db: Session = Depends(get_db)):
    """ТІЛЬКИ owner. MVP: без еквайрингу — кожен апгрейд пишеться в audit_log.

    Прод-вимога до паблік-запуску: LiqPay/Mono invoice + підтвердження вебхуком
    ПЕРЕД зміною plan (зараз — довірча зміна з аудитом)."""
    if new_plan not in PLANS:
        from fastapi import HTTPException
        raise HTTPException(400, f"Unknown plan. Available: {list(PLANS)}")
    from app.models import AuditLog
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    old = tenant.plan
    tenant.plan = new_plan
    db.add(AuditLog(tenant_id=user.tenant_id, actor_id=user.id,
                    entity_type="tenant", entity_id=str(tenant.id),
                    action="update",
                    old_values={"plan": old}, new_values={"plan": new_plan}))
    db.commit()
    return {"ok": True, "plan": new_plan, **PLANS[new_plan]}


@router.post("/invite-check")
def invite_check(user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """Викликати ПЕРЕД створенням нового user — перевірка ліміту місць."""
    check_seats(db, user.tenant_id)
    return {"ok": True, "message": "Є вільне місце"}
