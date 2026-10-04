"""Ізоляція тенантів (фаза 0.3): B не бачить і не чіпає обʼєкти A."""

from app.models import Client, Deal, Integration, Task

from tests.conftest import auth_headers, make_tenant, make_user


def _seed(db):
    import uuid as _uuid

    tag = _uuid.uuid4().hex[:6]
    ta = make_tenant(db, slug=f"ta-{tag}")
    tb = make_tenant(db, slug=f"tb-{tag}")
    ua = make_user(db, ta, role="manager", email=f"a-{tag}@t.ua")
    ub = make_user(db, tb, role="manager", email=f"b-{tag}@t.ua")
    ca = Client(tenant_id=ta.id, name="A-client", phone="+380501111111")
    db.add(ca)
    db.flush()
    da = Deal(tenant_id=ta.id, client_id=ca.id, title="A-deal", amount=10)
    db.add(da)
    db.add(Task(tenant_id=ta.id, title="A-task"))
    db.add(Integration(tenant_id=ta.id, provider="prom", credentials={}))
    db.commit()
    return ta, tb, ua, ub, ca, da


def test_clients_isolated(client, db):
    ta, tb, ua, ub, ca, da = _seed(db)
    hb = auth_headers(ub)
    r = client.get("/clients", headers=hb)
    assert r.status_code == 200 and r.json()["total"] == 0
    r = client.delete(f"/clients/{ca.id}", headers=hb)
    assert r.status_code == 404


def test_deals_tasks_isolated(client, db):
    ta, tb, ua, ub, ca, da = _seed(db)
    hb = auth_headers(ub)
    assert client.get("/deals", headers=hb).json()["total"] == 0
    assert client.patch(f"/deals/{da.id}/stage?stage=won", headers=hb).status_code == 404
    assert client.get("/tasks", headers=hb).json() == []


def test_analytics_requires_feature(client, db):
    ta, tb, ua, ub, ca, da = _seed(db)
    # обидва на free → 402 навіть на свої дані
    assert client.get("/analytics/kpi",
                      headers=auth_headers(ua)).status_code == 402


def _seed_full(db):
    """A з замовленням, діалогом, видом і правилом; B — порожній."""
    import uuid as _uuid

    from app.models import (AutomationRule, Conversation, Order, SavedView,
                            WebhookEvent)
    from app.services.orders import upsert_order

    tag = _uuid.uuid4().hex[:6]
    ta = make_tenant(db, slug=f"fa-{tag}")
    tb = make_tenant(db, slug=f"fb-{tag}")
    ua = make_user(db, ta, role="owner", email=f"oa-{tag}@t.ua")
    ub = make_user(db, tb, role="owner", email=f"ob-{tag}@t.ua")
    upsert_order(db, ta.id, {"source": "prom", "external_id": f"ord-{tag}",
                             "client_name": "А", "phone": "0501111111",
                             "total": 100}, origin="test")
    oid = db.query(Order).filter(Order.tenant_id == ta.id).first().id
    db.add(Conversation(tenant_id=ta.id, client_id=ca_id(db, ta),
                        channel="telegram", status="open"))
    db.add(SavedView(tenant_id=ta.id, user_id=ua.id, entity="deals",
                     name="Мої", filters={}))
    db.add(AutomationRule(tenant_id=ta.id, name="R", trigger_type="new_lead",
                          action_type="notify", created_by=ua.id))
    db.add(WebhookEvent(tenant_id=ta.id, provider="prom", external_id="e1",
                        payload={}))
    db.commit()
    return ta, tb, ua, ub, oid


def ca_id(db, tenant):
    from app.models import Client

    return db.query(Client).filter(Client.tenant_id == tenant.id).first().id


def test_orders_inbox_views_automations_audit_isolated(client, db):
    ta, tb, ua, ub, oid = _seed_full(db)
    hb = auth_headers(ub)
    assert client.get("/orders", headers=hb).json()["total"] == 0
    assert client.get(f"/orders/{oid}", headers=hb).status_code == 404
    assert client.patch(f"/orders/{oid}/status", headers=hb,
                        json={"status": "cancelled"}).status_code == 404
    assert client.get("/inbox/conversations", headers=hb).json() == []
    assert client.get("/views?entity=deals", headers=hb).json() == []
    assert client.get("/automations/rules", headers=hb).json() == []
    assert client.get("/audit", headers=hb).json() == []
    assert client.get("/billing/current", headers=hb).json()["plan"] == "free"
    # пошук B не знаходить клієнта A (той самий телефон)
    assert client.get("/search?q=0501111111", headers=hb).json()["clients"] == []
    # preview повідомлення по чужому клієнту — 404
    from app.models import Client

    other = db.query(Client).filter(Client.tenant_id == ta.id).first()
    assert client.get(f"/clients/{other.id}/message-preview?channel=telegram",
                      headers=hb).status_code == 404


def test_integrations_admin_isolated(client, db):
    ta, tb, ua, ub, oid = _seed_full(db)
    # B-адмін бачить лише свої (порожньо), а не інтеграцію A
    assert client.get("/integrations", headers=auth_headers(ub)).json() == []
    assert client.get("/webhooks/pending",
                      headers=auth_headers(ub)).json() == []
