"""Дії автоматизацій: кожен виконавець викликається і пише слід."""

import uuid

from tests.conftest import make_tenant, make_user


def _mk(db, role="owner"):
    t = make_tenant(db, slug=f"ac-{uuid.uuid4().hex[:6]}")
    u = make_user(db, t, role=role)
    return t, u


def _rule(t, action, trigger="new_lead", cfg=None):
    from app.models import AutomationRule

    return AutomationRule(tenant_id=t.id, name="R", trigger_type=trigger,
                          action_type=action, action_config=cfg or {})


def _client_deal(db, t, stage="new"):
    from app.models import Client, Deal

    c = Client(tenant_id=t.id, name="К", phone="+380501111111")
    db.add(c)
    db.flush()
    d = Deal(tenant_id=t.id, client_id=c.id, title="У", amount=1000, stage=stage)
    db.add(d)
    db.commit()
    return c, d


def test_assign_manager_round_robin(db):
    from app.services.actions import execute

    t, _ = _mk(db)
    m1 = make_user(db, t, role="manager")
    m2 = make_user(db, t, role="manager")
    c, d = _client_deal(db, t)
    d.manager_id = m1.id
    db.commit()
    ev = {"client_id": str(c.id)}
    execute(db, t.id, _rule(t, "assign_manager"), ev)
    assert ev["assigned_manager_id"] == str(m2.id)  # у m1 вже є відкрита
    db.commit()  # TestingSession без autoflush — фіксуємо перед refresh
    db.refresh(c)
    assert str(c.assigned_to) == str(m2.id)


def test_create_task_and_segment(db):
    from app.models import Task
    from app.services.actions import execute

    t, _ = _mk(db)
    c, d = _client_deal(db, t)
    execute(db, t.id, _rule(t, "create_task", cfg={"title": "T1"}),
            {"client_id": str(c.id), "deal_id": str(d.id)})
    assert db.query(Task).filter(Task.tenant_id == t.id,
                                 Task.title == "T1").count() == 1
    execute(db, t.id, _rule(t, "move_segment", cfg={"segment": "vip"}),
            {"client_id": str(c.id)})
    db.commit()
    db.refresh(c)
    assert c.segment == "vip"


def test_notify_request_review_unknown(db):
    import pytest

    from app.models import Interaction
    from app.services.actions import execute

    t, _ = _mk(db)
    c, d = _client_deal(db, t)
    execute(db, t.id, _rule(t, "notify", cfg={"title": "Ping"}),
            {"client_id": str(c.id)})
    assert db.query(Interaction).filter(
        Interaction.tenant_id == t.id).count() >= 1
    ev: dict = {}
    execute(db, t.id, _rule(t, "request_review"), ev)
    assert ev.get("_review_requested") is True
    with pytest.raises(ValueError):
        execute(db, t.id, _rule(t, "nope"), {})


def test_send_message_sms_stub(db):
    from app.services.actions import execute

    t, _ = _mk(db)
    c, d = _client_deal(db, t)
    ev = {"client_id": str(c.id), "deal_id": str(d.id)}
    execute(db, t.id, _rule(t, "send_message"), ev)
    assert ev["_message_sent"]["stub"] is True  # ключів нема — чесний stub


def test_create_ttn_errors_and_ok(db):
    import pytest

    from app.core.security import encrypt_credentials
    from app.integrations.novaposhta import NovaPoshtaAdapter
    from app.models import Integration
    from app.services.actions import execute

    t, _ = _mk(db)
    c, d = _client_deal(db, t)
    with pytest.raises(RuntimeError):
        execute(db, t.id, _rule(t, "create_ttn"), {})
    with pytest.raises(RuntimeError):
        execute(db, t.id, _rule(t, "create_ttn"), {"deal_id": str(d.id)})
    db.add(Integration(tenant_id=t.id, provider="novaposhta", is_active=True,
                       credentials=encrypt_credentials({"api_key": "k"})["enc"],
                       settings={}))
    db.commit()
    NovaPoshtaAdapter.create_ttn = lambda self, *a, **k: {
        "ok": True, "data": {"data": [{"IntDocNumber": "TTN9"}]}}
    try:
        ev = {"deal_id": str(d.id), "client_id": str(c.id)}
        execute(db, t.id, _rule(t, "create_ttn"), ev)
    finally:
        del NovaPoshtaAdapter.create_ttn
    assert ev["ttn"] == "TTN9"
