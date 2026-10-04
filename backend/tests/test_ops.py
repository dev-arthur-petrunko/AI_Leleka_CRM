"""Фонові операції: ТТН, підтвердження оплати, воркери розкладу."""

import uuid
from datetime import datetime, timedelta, UTC

from tests.conftest import make_tenant, make_user, auth_headers


def _order(client, db, h):
    r = client.post("/orders", headers=h, json={
        "source": "manual", "external_id": f"s-{uuid.uuid4().hex[:6]}",
        "client_name": "НП", "phone": "0501111111", "total": 500})
    assert r.status_code == 200
    return r.json()["id"]


def test_create_ttn_flow(client, db):
    from app.core.security import encrypt_credentials
    from app.integrations.novaposhta import NovaPoshtaAdapter
    from app.models import Integration

    t = make_tenant(db)
    u = make_user(db, t, role="owner")
    h = auth_headers(u)
    db.add(Integration(tenant_id=t.id, provider="novaposhta", is_active=True,
                       credentials=encrypt_credentials({"api_key": "k"})["enc"],
                       settings={"city_recipient": "Київ"}))
    db.commit()
    oid = _order(client, db, h)
    NovaPoshtaAdapter.create_ttn = lambda self, *a, **k: {
        "ok": True, "data": {"data": [{"IntDocNumber": "TTN123"}]}}
    try:
        r = client.post(f"/orders/{oid}/shipments", headers=h,
                        json={"carrier": "novaposhta", "cod_amount": 500})
    finally:
        del NovaPoshtaAdapter.create_ttn
    assert r.status_code == 200, r.text
    assert r.json()["ttn"] == "TTN123"
    d = client.get(f"/orders/{oid}", headers=h).json()
    assert any(s["ttn"] == "TTN123" for s in d["shipments"])
    # без підключеної НП — 404 з поясненням
    t2 = make_tenant(db)
    u2 = make_user(db, t2, role="owner")
    oid2 = _order(client, db, auth_headers(u2))
    r = client.post(f"/orders/{oid2}/shipments", headers=auth_headers(u2),
                    json={"carrier": "novaposhta"})
    assert r.status_code == 404


def test_confirm_paid_applies_plan(db):
    from app.api.billing import _confirm_paid
    from app.models import BillingOrder, Tenant

    t = make_tenant(db, plan="free")
    oid = f"test-{uuid.uuid4().hex[:8]}"
    db.add(BillingOrder(tenant_id=t.id, plan="pro", provider="liqpay",
                        order_id=oid, amount_uah=350, seats_billed=1,
                        status="pending"))
    db.commit()
    out = _confirm_paid(db, oid)
    assert out == {"ok": True, "plan": "pro"}
    assert db.query(Tenant).filter(Tenant.id == t.id).first().plan == "pro"
    # повтор — ідемпотентно
    assert _confirm_paid(db, oid)["message"] == "Уже оплачено"


def test_stuck_checker_finds_old_deal(db):
    from app.models import Client, Deal
    from app.workers.stuck_checker import check_stuck

    t = make_tenant(db)
    c = Client(tenant_id=t.id, name="С", phone="+380501111111")
    db.add(c)
    db.flush()
    db.add(Deal(tenant_id=t.id, client_id=c.id, title="Зависла",
                amount=100, stage="new",
                last_activity_at=datetime.now(UTC) - timedelta(days=10)))
    db.commit()
    out = check_stuck(days=3)
    assert out["stuck_found"] >= 1


def test_billing_recalc_delta(db):
    from app.workers.billing_recalc import recalc

    t = make_tenant(db, slug=f"bl-{uuid.uuid4().hex[:6]}", plan="pro")
    make_user(db, t, role="owner")
    make_user(db, t, role="manager")
    out = {r["tenant"]: r for r in recalc()}
    assert out[t.slug]["seats_now"] == 2
    assert out[t.slug]["delta"] == 2  # оплачених рахунків не було


def test_feed_scheduler_empty(db):
    from app.workers.feed_scheduler import run_due

    assert run_due() == [] or isinstance(run_due(), list)


def test_confirm_email_flow(client, db):
    from app.api.auth import _confirm_token, _verify_confirm_token

    email = f"ce-{uuid.uuid4().hex[:6]}@t.ua"
    r = client.post("/auth/register", json={
        "tenant_name": "C", "slug": f"cf-{uuid.uuid4().hex[:6]}",
        "owner_name": "O", "email": email, "password": "Longpassword123"})
    assert r.status_code == 200
    tok = r.json()["access_token"]
    assert client.get("/auth/me",
                      headers={"Authorization": f"Bearer {tok}"}).json()["email_confirmed"] is False
    assert client.post("/auth/confirm-email",
                       json={"token": "bad"}).status_code == 400
    assert _verify_confirm_token("bad") is None
    r = client.post("/auth/confirm-email",
                    json={"token": _confirm_token(email)})
    assert r.json() == {"ok": True, "email": email}
    assert client.get("/auth/me",
                      headers={"Authorization": f"Bearer {tok}"}).json()["email_confirmed"] is True
