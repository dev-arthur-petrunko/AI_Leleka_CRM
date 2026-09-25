from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_tenant, get_current_user
from app.db.session import get_db
from app.models import AutomationLog, AutomationRule, User

router = APIRouter(prefix="/automations", tags=["automations"])


class RuleIn(BaseModel):
    name: str
    trigger_type: str  # new_lead | deal_stuck | payment_received | no_response | deal_won | deal_lost
    trigger_config: dict = {}
    action_type: str   # assign_manager | notify | create_ttn | send_message | request_review | move_segment | create_task
    action_config: dict = {}
    is_active: bool = True
    priority: int = 0


@router.get("/rules")
def list_rules(tenant_id: UUID = Depends(get_current_tenant),
               db: Session = Depends(get_db)):
    return db.query(AutomationRule).filter(
        AutomationRule.tenant_id == tenant_id
    ).order_by(AutomationRule.priority.desc()).all()


@router.post("/rules")
def create_rule(data: RuleIn, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    rule = AutomationRule(tenant_id=user.tenant_id, created_by=user.id,
                          **data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    # seed: если это первая rule в tenant — сразу видно в /stats
    return rule


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: UUID, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    rule = db.query(AutomationRule).filter(
        AutomationRule.id == rule_id, AutomationRule.tenant_id == user.tenant_id
    ).first()
    if not rule:
        raise HTTPException(404, "Not found")
    db.delete(rule)
    db.commit()
    return {"ok": True}


@router.get("/logs")
def list_logs(tenant_id: UUID = Depends(get_current_tenant),
              db: Session = Depends(get_db), limit: int = 50):
    return db.query(AutomationLog).filter(
        AutomationLog.tenant_id == tenant_id
    ).order_by(AutomationLog.created_at.desc()).limit(limit).all()


@router.get("/stats")
def stats(tenant_id: UUID = Depends(get_current_tenant),
          db: Session = Depends(get_db)):
    """«Сработало 15 раз, 2 с ошибкой» — по каждой rule."""
    rows = db.query(
        AutomationLog.rule_id, AutomationLog.status, func.count(AutomationLog.id)
    ).filter(AutomationLog.tenant_id == tenant_id)\
     .group_by(AutomationLog.rule_id, AutomationLog.status).all()
    out: dict[str, dict] = {}
    for rule_id, status, cnt in rows:
        out.setdefault(str(rule_id), {}).__setitem__(status, cnt)
    return out


@router.post("/seed-defaults")
def seed_defaults(user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """5 правил из ТЗ одним кликом — для демо и бета-теста."""
    defaults = [
        ("Новый лид -> назначить менеджера", "new_lead", {},
         "assign_manager", {}, 100),
        ("Зависла 3 дня -> напомнить", "deal_stuck", {"stuck_days": 3},
         "create_task", {"title": "Угода зависла! Зателефонувати"}, 90),
        ("Оплата -> ТТН + чек", "payment_received", {},
         "create_ttn", {"provider": "novaposhta"}, 80),
        ("Мовчить 24г -> повторний лист", "no_response", {"hours": 24},
         "send_message", {"template": "followup_24h"}, 70),
        ("Угода виграна -> відгук + VIP", "deal_won", {},
         "request_review", {}, 60),
    ]
    created = 0
    for name, trig, tcfg, act, acfg, prio in defaults:
        exists = db.query(AutomationRule).filter(
            AutomationRule.tenant_id == user.tenant_id,
            AutomationRule.name == name).first()
        if not exists:
            db.add(AutomationRule(
                tenant_id=user.tenant_id, name=name, trigger_type=trig,
                trigger_config=tcfg, action_type=act, action_config=acfg,
                priority=prio, created_by=user.id))
            created += 1
    db.commit()
    return {"created": created}
