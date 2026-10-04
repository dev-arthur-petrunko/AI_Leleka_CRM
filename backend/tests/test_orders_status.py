"""Скасування замовлення менеджером + історія + ізоляція."""

from tests.conftest import make_tenant, make_user, auth_headers


def _mk(client, db):
    t = make_tenant(db)
    u = make_user(db, t, role="manager")
    h = auth_headers(u)
    r = client.post("/orders", headers=h, json={
        "source": "manual", "external_id": "c1", "client_name": "К",
        "total": 100})
    assert r.status_code == 200
    return t, u, h, r.json()["id"]


def test_cancel_order_flow(client, db):
    t, u, h, oid = _mk(client, db)
    # підтвердили...
    assert client.patch(f"/orders/{oid}/status", headers=h,
                        json={"status": "confirmed"}).status_code == 200
    # ...ой, скасовуємо
    r = client.patch(f"/orders/{oid}/status", headers=h,
                     json={"status": "cancelled"})
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    # історія записала обидва переходи з source=manager
    d = client.get(f"/orders/{oid}", headers=h).json()
    hist = [(x["from_status"], x["to_status"], x["source"]) for x in d["history"]]
    assert ("new", "confirmed", "manager") in hist
    assert ("confirmed", "cancelled", "manager") in hist
    # ...і повертаємо в роботу
    r = client.patch(f"/orders/{oid}/status", headers=h, json={"status": "new"})
    assert r.json()["status"] == "new"


def test_cancel_validation_and_isolation(client, db):
    t, u, h, oid = _mk(client, db)
    assert client.patch(f"/orders/{oid}/status", headers=h,
                        json={"status": "wtf"}).status_code == 400
    t2 = make_tenant(db)
    u2 = make_user(db, t2, role="manager")
    assert client.patch(f"/orders/{oid}/status", headers=auth_headers(u2),
                        json={"status": "cancelled"}).status_code == 404
    assert client.patch(f"/orders/{oid}/status",
                        json={"status": "cancelled"}).status_code == 401
