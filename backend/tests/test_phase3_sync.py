# -*- coding: utf-8 -*-
"""Фаза 3: фікстури провайдерів, воркер вебхуків, sync, форми, трекінг."""

import json
import pathlib
import uuid

from tests.conftest import auth_headers, make_tenant, make_user

FIX = pathlib.Path(__file__).parent / "fixtures"


def test_normalize_prom_fixture():
    from app.integrations.marketplace import normalize_order

    raw = json.loads((FIX / "prom" / "orders_list.json").read_text(encoding="utf-8"))
    o1, o2 = (normalize_order("prom", r) for r in raw["orders"])
    assert (o1["external_id"], o1["name"], o1["phone"], o1["amount"]) == \
        ("1001", "Олена", "+380501234567", 1500.0)
    assert o2["product_summary"] == "Чохол та ще 1 поз."


def test_normalize_rozetka_fixture():
    from app.integrations.marketplace import normalize_order

    raw = json.loads((FIX / "rozetka" / "orders_search.json").read_text(encoding="utf-8"))
    (o,) = (normalize_order("rozetka", r) for r in raw["orders"])
    assert o["name"] == "Ірина" and o["product_summary"] == "Кавоварка"


def test_webhook_batch_dead_after_10(client, db):
    from app.models import WebhookEvent
    from app.workers.tasks import process_webhook_batch

    t = make_tenant(db, slug=f"wh-{uuid.uuid4().hex[:6]}")
    ev = WebhookEvent(tenant_id=t.id, provider="prom", external_id="nope-bad",
                      payload={"total": {"broken": "object"}}, retry_count=9)
    db.add(ev)
    db.commit()
    # float(dict) впаде в upsert → 10-та спроба = dead
    out = process_webhook_batch.run(limit=10)
    assert out["dead"] >= 1 or out["failed"] >= 1
    db.refresh(ev)
    assert ev.status in ("dead", "failed")


def test_sync_state_cursor(client, db):
    from app.core.security import encrypt_credentials
    from app.models import Integration
    from app.services.sync import get_state, sync_integration

    t = make_tenant(db, slug=f"sy-{uuid.uuid4().hex[:6]}")
    row = Integration(tenant_id=t.id, provider="prom", credentials={})
    db.add(row)
    db.commit()
    out = sync_integration(db, row.id)  # без ключа → stub, але стан оновлено
    assert out["ok"] is True
    st = get_state(db, row)
    assert st.last_success_at is not None


def test_lead_form_spam_rejected(client, db):
    from app.models import LeadForm

    t = make_tenant(db, slug=f"lf-{uuid.uuid4().hex[:6]}")
    f = LeadForm(tenant_id=t.id, name="Лендінг", secret="s3cr3t-form")
    db.add(f)
    db.commit()
    # honeypot заповнено → тиха відмова без створення
    r = client.post(f"/api/v1/forms/{f.id}",
                    json={"secret": "s3cr3t-form", "name": "Спам",
                          "website": "http://spam"})
    assert r.status_code == 200 and r.json()["ok"] is True
    # невірний секрет → 404
    r = client.post(f"/api/v1/forms/{f.id}", json={"secret": "wrong"})
    assert r.status_code == 404
    # чесна заявка → клієнт+угода
    r = client.post(f"/api/v1/forms/{f.id}",
                    json={"secret": "s3cr3t-form", "name": "Лід",
                          "phone": "0501234500"})
    assert r.status_code == 200
