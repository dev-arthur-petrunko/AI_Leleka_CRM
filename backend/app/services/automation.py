"""Движок автоматизаций «если -> то».

run_automations(db, tenant_id, trigger_type, event) — точка входа.
- Находит активные rules для tenant+trigger (по priority DESC).
- Проверяет trigger_config (stages, stuck_days...).
- Выполняет action через actions.py.
- Пишет AutomationLog (success/failed/skipped) — без него отладка невозможна.
"""

import time
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AutomationLog, AutomationRule


def _conditions_ok(rule: AutomationRule, event: dict) -> bool:
    cfg = rule.trigger_config or {}
    # фильтр по stages: {"stages": ["contacted", "negotiation"]}
    if "stages" in cfg and event.get("stage") not in cfg["stages"]:
        return False
    # фильтр мин. суммы: {"min_amount": 1000}
    if "min_amount" in cfg and (event.get("amount") or 0) < cfg["min_amount"]:
        return False
    return True


def run_automations(
    db: Session, tenant_id: UUID, trigger_type: str, event: dict
) -> list[AutomationLog]:
    from app.services import actions  # локальный импорт от циклов

    rules = (
        db.query(AutomationRule)
        .filter(
            AutomationRule.tenant_id == tenant_id,
            AutomationRule.trigger_type == trigger_type,
            AutomationRule.is_active.is_(True),
        )
        .order_by(AutomationRule.priority.desc())
        .all()
    )
    logs: list[AutomationLog] = []
    for rule in rules:
        if not _conditions_ok(rule, event):
            logs.append(_write_log(db, tenant_id, rule, event, "skipped", None, 0))
            continue
        start = time.perf_counter()
        try:
            actions.execute(db, tenant_id, rule, event)
            ms = int((time.perf_counter() - start) * 1000)
            logs.append(_write_log(db, tenant_id, rule, event, "success", None, ms))
        except Exception as e:  # noqa: BLE001 — обязаны залогировать, не уронить запрос
            ms = int((time.perf_counter() - start) * 1000)
            logs.append(_write_log(db, tenant_id, rule, event, "failed", str(e), ms))
    db.commit()
    return logs


def _write_log(db: Session, tenant_id: UUID, rule: AutomationRule,
               event: dict, status: str, error: str | None, ms: int) -> AutomationLog:
    log = AutomationLog(
        tenant_id=tenant_id, rule_id=rule.id,
        trigger_event=event, status=status,
        error_message=error, execution_ms=ms,
    )
    db.add(log)
    db.flush()
    return log
