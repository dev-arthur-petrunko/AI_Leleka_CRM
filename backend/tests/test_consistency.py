# -*- coding: utf-8 -*-
"""Тест узгодженості цифр (UI 6.2): аналітика == таблиці. Розбіжність роняє CI."""

import uuid

from tests.conftest import auth_headers, make_tenant, make_user


def _mk(db, tag):
    from datetime import datetime, timezone

    from app.models import Client, Deal, Order

    t = make_tenant(db, slug=f"con-{tag}", plan="pro")
    u = make_user(db, t, role="owner", email=f"c-{tag}@t.ua")
    c = Client(tenant_id=t.id, name="C")
    db.add(c)
    db.flush()
    now = datetime.now(timezone.utc)
    for i, (st, amt) in enumerate([("new", 100), ("new", 200), ("won", 300)]):
        db.add(Deal(tenant_id=t.id, client_id=c.id, title=f"d{i}",
                    amount=amt, stage=st, last_activity_at=now,
                    won_at=now if st == "won" else None))
    db.add(Order(tenant_id=t.id, client_id=c.id, source="manual",
                 external_id="o1", status="delivered", payment_status="paid",
                 total=300, placed_at=now))
    db.commit()
    return t, u


def test_pipeline_sum_matches(client, db):
    tag = uuid.uuid4().hex[:6]
    t, u = _mk(db, tag)
    h = auth_headers(u)
    funnel = {f["stage"]: f["count"]
              for f in client.get("/analytics/funnel", headers=h).json()}
    assert funnel.get("new") == 2 and funnel.get("won") == 1
    deals = client.get("/deals?limit=100", headers=h).json()
    open_sum = sum(x["amount"] for x in deals["items"] if x["stage"] not in ("won", "lost"))
    assert open_sum == 300
    kpi = client.get("/analytics/kpi", headers=h).json()
    assert kpi["won_total"] == 1


def test_avg_check_matches_revenue(client, db):
    tag = uuid.uuid4().hex[:6]
    t, u = _mk(db, tag)
    h = auth_headers(u)
    rev = client.get("/analytics/shop/revenue?days=365", headers=h).json()
    assert rev["aov"] == 300.0
    assert rev["by_day"][0]["total"] == 300.0


def test_lost_excluded_from_churn(client, db):
    from datetime import datetime, timedelta, timezone

    from app.models import Client, Deal
    from app.services import ai as _ai

    tag = uuid.uuid4().hex[:6]
    t = make_tenant(db, slug=f"ch-{tag}")
    make_user(db, t, role="owner")
    old = datetime.now(timezone.utc) - timedelta(days=60)
    c = Client(tenant_id=t.id, name="Lost", segment="lost")
    db.add(c)
    db.flush()
    db.add(Deal(tenant_id=t.id, client_id=c.id, title="x", amount=10,
                stage="lost", last_activity_at=old))
    db.commit()
    ids = [x["client_id"] for x in _ai.churn_candidates(db, t.id)]
    assert str(c.id) not in ids


def test_convert_idempotent(client, db):
    tag = uuid.uuid4().hex[:6]
    t, u = _mk(db, tag)
    h = auth_headers(u)
    from app.models import Deal

    d = db.query(Deal).filter(Deal.tenant_id == t.id, Deal.stage == "new").first()
    r1 = client.post(f"/deals/{d.id}/convert-to-order", headers=h, json={"total": 100})
    r2 = client.post(f"/deals/{d.id}/convert-to-order", headers=h, json={"total": 100})
    assert r1.json()["order_id"] == r2.json()["order_id"]
    assert r2.json()["deduplicated"] is True
    # lost без причини — 400
    r3 = client.patch(f"/deals/{d.id}/stage?stage=lost", headers=h)
    assert r3.status_code == 400
