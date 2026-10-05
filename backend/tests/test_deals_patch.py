"""Редагування угоди: поля, валідація, ізоляція."""

from tests.conftest import make_tenant, make_user, auth_headers


def _mk(client, db):
    from app.models import Client

    t = make_tenant(db)
    u = make_user(db, t, role="manager")
    c = Client(tenant_id=t.id, name="К", phone="+380501111111")
    db.add(c)
    db.commit()
    h = auth_headers(u)
    r = client.post("/deals", headers=h, json={
        "client_id": str(c.id), "title": "Стара", "amount": 100})
    assert r.status_code == 200
    return t, u, h, c, r.json()["id"]


def test_deal_patch_flow(client, db):
    t, u, h, c, did = _mk(client, db)
    r = client.patch(f"/deals/{did}", headers=h, json={
        "title": "Нова назва", "amount": 250, "probability": 60})
    assert r.status_code == 200
    body = r.json()
    assert (body["title"], float(body["amount"]), body["probability"]) == \
        ("Нова назва", 250.0, 60)
    assert body["stage"] == "new"  # стадію PATCH не чіпає
    assert client.patch(f"/deals/{did}", headers=h,
                        json={"title": "  "}).status_code == 400
    assert client.patch(f"/deals/{did}", headers=h,
                        json={"amount": -5}).status_code == 400
    assert client.patch(f"/deals/{did}", headers=h,
                        json={"probability": 101}).status_code == 400


def test_deal_patch_isolation(client, db):
    import uuid

    from app.models import Client

    t, u, h, c, did = _mk(client, db)
    t2 = make_tenant(db, slug=f"dx-{uuid.uuid4().hex[:6]}")
    u2 = make_user(db, t2, role="manager")
    c2 = Client(tenant_id=t2.id, name="Чужий", phone="+380502222222")
    db.add(c2)
    db.commit()
    h2 = auth_headers(u2)
    # чужа угода — 404
    assert client.patch(f"/deals/{did}", headers=h2,
                        json={"title": "X"}).status_code == 404
    # чужий клієнт/менеджер — 400
    assert client.patch(f"/deals/{did}", headers=h,
                        json={"client_id": str(c2.id)}).status_code == 400
    assert client.patch(f"/deals/{did}", headers=h,
                        json={"manager_id": str(u2.id)}).status_code == 400
    # без токена — 401
    assert client.patch(f"/deals/{did}",
                        json={"title": "X"}).status_code == 401


def test_deal_unlink_order_flow(client, db):
    t, u, h, c, did = _mk(client, db)
    # без звʼязку — 400
    assert client.post(f"/deals/{did}/unlink-order",
                       headers=h).status_code == 400
    # конвертуємо, потім розриваємо
    r = client.post(f"/deals/{did}/convert-to-order", headers=h, json={})
    assert r.status_code == 200
    oid = r.json()["order_id"]
    r = client.post(f"/deals/{did}/unlink-order", headers=h)
    assert r.json() == {"ok": True, "order_id": oid}
    # замовлення ЖИВЕ в «Замовленнях», звʼязку нема
    assert client.get(f"/orders/{oid}", headers=h).status_code == 200
    patched = [x for x in (client.get("/deals", headers=h).json()["items"])
               if x["id"] == did][0]
    assert patched["converted_order_id"] is None
    # чужий тенант — 404, без токена — 401
    t2 = make_tenant(db)
    u2 = make_user(db, t2, role="manager")
    assert client.post(f"/deals/{did}/unlink-order",
                       headers=auth_headers(u2)).status_code == 404
    assert client.post(f"/deals/{did}/unlink-order").status_code == 401
