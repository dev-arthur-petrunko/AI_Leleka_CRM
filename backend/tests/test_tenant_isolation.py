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
