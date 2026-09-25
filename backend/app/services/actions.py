"""Исполнители действий. Каждое действие — маленькая функция.

MVP-реализация:
- assign_manager: round-robin — менеджер с мин. числом открытых угод
- create_task: создает задачу из action_config
- move_segment: переносит клиента в сегмент (regular/vip/...)
- notify / send_message / request_review / create_ttn: stub — пишут в лог,
  реальные отправки (SMS/Nova Poshta/Checkbox) подключаются адаптерами позже.
"""

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AutomationRule, Client, Deal, Task, User


def execute(db: Session, tenant_id: UUID, rule: AutomationRule, event: dict) -> None:
    handler = {
        "assign_manager": _assign_manager,
        "create_task": _create_task,
        "move_segment": _move_segment,
        "notify": _notify,
        "send_message": _send_message,
        "request_review": _request_review,
        "create_ttn": _create_ttn,
    }.get(rule.action_type)
    if not handler:
        raise ValueError(f"Unknown action: {rule.action_type}")
    handler(db, tenant_id, rule, event)


def _assign_manager(db: Session, tenant_id: UUID, rule: AutomationRule, event: dict):
    managers = db.query(User).filter(
        User.tenant_id == tenant_id,
        User.role.in_(["manager", "admin"]),
        User.is_active.is_(True),
    ).all()
    if not managers:
        raise RuntimeError("No active managers for round-robin")
    # round-robin MVP: у кого меньше открытых сделок — тому и лид
    counts = dict(
        db.query(Deal.manager_id, func.count(Deal.id))
        .filter(Deal.tenant_id == tenant_id, Deal.stage.notin_(["won", "lost"]))
        .group_by(Deal.manager_id).all()
    )
    chosen = min(managers, key=lambda m: counts.get(m.id, 0))
    client_id = event.get("client_id")
    if client_id:
        client = db.query(Client).filter(
            Client.id == client_id, Client.tenant_id == tenant_id
        ).first()
        if client:
            client.assigned_to = chosen.id
    # пробрасываем выбор дальше по цепочке event
    event["assigned_manager_id"] = str(chosen.id)


def _create_task(db: Session, tenant_id: UUID, rule: AutomationRule, event: dict):
    cfg = rule.action_config or {}
    task = Task(
        tenant_id=tenant_id,
        title=cfg.get("title", f"Auto: {rule.name}"),
        description=cfg.get("description", ""),
        assignee_id=_as_uuid(event.get("assigned_manager_id") or event.get("manager_id")),
        client_id=_as_uuid(event.get("client_id")),
        deal_id=_as_uuid(event.get("deal_id")),
        priority=cfg.get("priority", "high" if rule.trigger_type == "deal_stuck" else "normal"),
    )
    db.add(task)
    db.flush()


def _move_segment(db: Session, tenant_id: UUID, rule: AutomationRule, event: dict):
    cfg = rule.action_config or {}
    target = cfg.get("segment", "regular")
    client = db.query(Client).filter(
        Client.id == event.get("client_id"), Client.tenant_id == tenant_id
    ).first() if event.get("client_id") else None
    if not client:
        raise RuntimeError("move_segment: client not found in event")
    client.segment = target
    db.flush()


def _notify(db: Session, tenant_id: UUID, rule: AutomationRule, event: dict):
    # MVP: уведомление = задача руководителю; реальный Telegram/SMS — позже
    cfg = rule.action_config or {}
    db.add(Task(
        tenant_id=tenant_id,
        title=cfg.get("title", f"Уведомление: {rule.name}"),
        description=cfg.get("text", str(event))[:2000],
        priority="high",
    ))
    db.flush()


def _send_message(db: Session, tenant_id: UUID, rule: AutomationRule, event: dict):
    # Stub: реальная отправка через SendPulse/SMS-провайдера — отдельный адаптер.
    # Фиксируем намерение в event чтобы было видно в automation_logs.
    event["_message_queued"] = (rule.action_config or {}).get("template", "followup_24h")


def _request_review(db: Session, tenant_id: UUID, rule: AutomationRule, event: dict):
    event["_review_requested"] = True


def _create_ttn(db: Session, tenant_id: UUID, rule: AutomationRule, event: dict):
    # Stub: создание ТТН Новой Пошты — адаптер integrations(provider='novaposhta').
    if not event.get("deal_id"):
        raise RuntimeError("create_ttn: no deal_id in event")
    event["_ttn_queued"] = True


def _as_uuid(value):
    if not value:
        return None
    from uuid import UUID as _UUID
    try:
        return value if isinstance(value, _UUID) else _UUID(str(value))
    except Exception:
        return None
