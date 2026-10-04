"""Сегмент клієнта: зміна, валідація, ізоляція."""

from tests.conftest import make_tenant, make_user, auth_headers


def test_client_segment_flow(client, db):
    from app.models import Client

    t = make_tenant(db)
    u = make_user(db, t, role="manager")
    h = auth_headers(u)
    c = Client(tenant_id=t.id, name="Олена", phone="+380501234567", segment="new")
    db.add(c)
    db.commit()
    cid = str(c.id)
    r = client.patch(f"/clients/{cid}", headers=h, json={"segment": "vip"})
    assert r.status_code == 200 and r.json()["segment"] == "vip"
    r = client.patch(f"/clients/{cid}", headers=h, json={"segment": "regular"})
    assert r.json()["segment"] == "regular"
    assert client.patch(f"/clients/{cid}", headers=h,
                        json={"segment": "wtf"}).status_code == 400
    # телефон нормалізується
    r = client.patch(f"/clients/{cid}", headers=h, json={"phone": "0501234567"})
    assert r.json()["phone"] == "+380501234567"
    # чужий тенант — 404, без токена — 401
    t2 = make_tenant(db)
    u2 = make_user(db, t2, role="manager")
    assert client.patch(f"/clients/{cid}", headers=auth_headers(u2),
                        json={"segment": "vip"}).status_code == 404
    assert client.patch(f"/clients/{cid}",
                        json={"segment": "vip"}).status_code == 401
