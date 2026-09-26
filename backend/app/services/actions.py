"""Исполнители действий. Кожна дія — маленька функція.

- assign_manager: round-robin — менеджер з мін. числом відкритих угод
- create_task / move_segment / request_review — локальні дії в БД
- notify: Redis-інбокс (GET /notifications) + задача-бекап, якщо Redis недоступний
- send_message: реальна відправка через SendPulse/TurboSMS (ключ у integrations),
  без ключа — чесний stub + запис у interactions(channel='auto')
- create_ttn: реальне створення ТТН через NovaPoshtaAdapter (ключ у integrations),
  номер ТТН пишеться в event['ttn'] і в interactions
"""

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import decrypt_credentials
from app.models import AutomationRule, Client, Deal, Integration, Interaction, Task, User
from app.services import notify as notify_queue


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
    cfg = rule.action_config or {}
    text = cfg.get("title", f"Сповіщення: {rule.name}")
    pushed = notify_queue.push(tenant_id, text, kind="notify", ref=event)
    if not pushed:
        # Redis недоступний — задача як бекап, щоб сповіщення не загубилось
        db.add(Task(tenant_id=tenant_id, title=text,
                    description=cfg.get("text", str(event))[:2000], priority="high"))
        db.flush()
    _auto_interaction(db, tenant_id, event, f"notify: {text}")


def _send_message(db: Session, tenant_id: UUID, rule: AutomationRule, event: dict):
    from app.integrations.sms import SendPulseAdapter, TurboSmsAdapter

    cfg = rule.action_config or {}
    template = cfg.get("template", "followup_24h")
    client = _event_client(db, tenant_id, event)
    phone = (client.phone or "") if client else ""
    text = cfg.get("text", f"Доброго дня! Нагадуємо про ваше замовлення (шаблон {template}).")
    sent: dict = {"ok": True, "stub": True}
    for provider, adapter_cls in (("sendpulse", SendPulseAdapter), ("turbosms", TurboSmsAdapter)):
        row = _integration(db, tenant_id, provider)
        if row and phone:
            creds = decrypt_credentials(row.credentials)
            sent = adapter_cls(creds, row.settings).send_sms(phone, text)
            if sent.get("ok"):
                break
    event["_message_sent"] = sent
    _auto_interaction(db, tenant_id, event,
                      f"sms({'real' if not sent.get('stub') else 'stub'}): {text[:120]}")


def _request_review(db: Session, tenant_id: UUID, rule: AutomationRule, event: dict):
    event["_review_requested"] = True
    _auto_interaction(db, tenant_id, event, "request_review: запит на відгук")


def _create_ttn(db: Session, tenant_id: UUID, rule: AutomationRule, event: dict):
    from app.integrations.novaposhta import NovaPoshtaAdapter

    if not event.get("deal_id"):
        raise RuntimeError("create_ttn: no deal_id in event")
    row = _integration(db, tenant_id, "novaposhta")
    client = _event_client(db, tenant_id, event)
    deal = db.query(Deal).filter(
        Deal.id == event["deal_id"], Deal.tenant_id == tenant_id).first()
    if row is None:
        raise RuntimeError("create_ttn: підключіть Нову Пошту через POST /integrations")
    creds = decrypt_credentials(row.credentials)
    adapter = NovaPoshtaAdapter(creds, row.settings)
    resp = adapter.create_ttn(
        recipient_phone=(client.phone or "") if client else "",
        recipient_city=(row.settings or {}).get("city_recipient", "Київ"),
        cod=float(deal.amount or 0) if deal else 0,
    )
    if not resp.get("ok"):
        raise RuntimeError(f"create_ttn: {resp.get('error')}")
    # Витягаємо номер ТТН з відповіді НП (або stub-мітку)
    data = resp.get("data") or {}
    ttn = None
    try:
        ttn = (data.get("data") or [{}])[0].get("IntDocNumber")
    except Exception:
        ttn = None
    event["ttn"] = ttn or ("STUB" if resp.get("stub") else "created")
    if deal and ttn and ttn != "STUB":
        deal.title = f"{deal.title} [ТТН {ttn}]"
    _auto_interaction(db, tenant_id, event, f"ttn: {event['ttn']}")


def _integration(db: Session, tenant_id: UUID, provider: str):
    return db.query(Integration).filter(
        Integration.tenant_id == tenant_id, Integration.provider == provider,
        Integration.is_active.is_(True)).first()


def _event_client(db: Session, tenant_id: UUID, event: dict):
    if not event.get("client_id"):
        return None
    return db.query(Client).filter(
        Client.id == event["client_id"], Client.tenant_id == tenant_id).first()


def _auto_interaction(db: Session, tenant_id: UUID, event: dict, body: str):
    """Кожна дія автоматизації залишає слід у таймлайні клієнта."""
    if not event.get("client_id"):
        return
    db.add(Interaction(tenant_id=tenant_id, client_id=_as_uuid(event["client_id"]),
                       deal_id=_as_uuid(event.get("deal_id")), channel="auto", body=body))
    db.flush()


def _as_uuid(value):
    if not value:
        return None
    from uuid import UUID as _UUID
    try:
        return value if isinstance(value, _UUID) else _UUID(str(value))
    except Exception:
        return None
