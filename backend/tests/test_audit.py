"""Журнал аудиту: читає тільки свій тенант."""

from tests.conftest import make_tenant, make_user, auth_headers


def test_audit_isolated(client, db):
    from app.models import AuditLog

    t = make_tenant(db)
    u = make_user(db, t, role="owner")
    db.add(AuditLog(tenant_id=t.id, actor_id=u.id, entity_type="client",
                    entity_id="x", action="test"))
    db.commit()
    r = client.get("/audit", headers=auth_headers(u))
    assert r.status_code == 200 and any(x["action"] == "test" for x in r.json())
    # чужий тенант не бачить
    t2 = make_tenant(db)
    u2 = make_user(db, t2, role="owner")
    r2 = client.get("/audit", headers=auth_headers(u2))
    assert r2.status_code == 200 and r2.json() == []
    # без токена — 401
    assert client.get("/audit").status_code == 401
