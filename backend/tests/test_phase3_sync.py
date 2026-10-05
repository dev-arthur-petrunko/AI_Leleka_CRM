"""Фаза 3: фікстури провайдерів, воркер вебхуків, sync, форми, трекінг."""

import json
import pathlib
import uuid

from tests.conftest import make_tenant

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
    from app.models import Integration
    from app.services.sync import get_state, sync_integration

    t = make_tenant(db, slug=f"sy-{uuid.uuid4().hex[:6]}")
    row = Integration(tenant_id=t.id, provider="prom", credentials={})
    db.add(row)
    db.commit()
    # без ключа — НЕ ok: чесний статус not_connected
    out = sync_integration(db, row.id)
    assert out["ok"] is False and out["error"] == "not_connected"
    db.refresh(row)
    assert row.status == "not_connected"
    st = get_state(db, row)
    assert st.last_success_at is None


def _keyed(db, t, provider="prom"):
    from app.core.security import encrypt_credentials
    from app.models import Integration

    row = Integration(tenant_id=t.id, provider=provider,
                      credentials=encrypt_credentials({"token": "k"})["enc"])
    db.add(row)
    db.commit()
    return row


def test_sync_cursor_items_stable_ids(client, db):
    from app.models import Order
    from app.services.sync import get_state, sync_integration

    t = make_tenant(db, slug=f"sc-{uuid.uuid4().hex[:6]}")
    row = _keyed(db, t)
    pages = [
        {"ok": True, "data": {"orders": [
            {"id": 1, "client_first_name": "А", "client_phone": "0501111111",
             "price": 100, "date_created": "2026-09-01",
             "products": [{"name": "Чохол", "price": 100, "quantity": 2}]},
            {"client_first_name": "Б", "client_phone": "0502222222",
             "price": 200, "date_created": "2026-09-02",
             "products": [{"name": "Кава"}]},
        ]}},
        {"ok": True, "data": {"orders": []}},
    ]
    calls = []

    def fake(self, limit=100, date_from=None, **kw):
        calls.append(date_from)
        return pages.pop(0) if pages else {"ok": True, "data": {"orders": []}}

    import app.integrations.marketplace as mp
    import app.services.sync as syncmod
    mp.PromAdapter.pull_orders = fake
    syncmod.PAGE_LIMIT = 2  # сторінка повна → йдемо за наступною
    try:
        out = sync_integration(db, row.id)
        assert out == {"ok": True, "imported": 2}, out
        # повторний запуск — жодних дублей (стабільний sync-хеш без id)
        out2 = sync_integration(db, row.id)
        assert out2 == {"ok": True, "imported": 0}, out2
    finally:
        del mp.PromAdapter.pull_orders
        syncmod.PAGE_LIMIT = 100
    # друга сторінка пішла з курсором = датою останнього (нормалізована)
    assert calls[1] == "2026-09-02T00:00:00+00:00", calls
    st = get_state(db, row)
    assert st.cursor == "2026-09-02T00:00:00+00:00"
    # позиції збережено
    items = db.query(Order).filter(Order.tenant_id == t.id).all()
    assert len(items) == 2
    o1 = next(o for o in items if o.external_id == "1")
    from app.models import OrderItem
    it = db.query(OrderItem).filter(OrderItem.order_id == o1.id).all()
    assert [(x.name, x.qty, float(x.unit_price)) for x in it] == [("Чохол", 2.0, 100.0)]
    assert db.query(Order).filter(Order.tenant_id == t.id).count() == 2


def test_sync_hash_stable_without_position(client, db):
    from app.services.sync import norm_date, stable_external_id

    raw = {"client_first_name": "Б", "price": 200}
    assert stable_external_id("prom", raw) == stable_external_id("prom", dict(raw))
    # ті самі дані в іншому порядку ключів — той самий id
    assert stable_external_id("prom", {"price": 200, "client_first_name": "Б"}) == \
        stable_external_id("prom", raw)
    assert norm_date({"date_created": "2026-09-02"}).startswith("2026-09-02T00:00:00")
    assert norm_date({"created": "02.09.2026 10:00"}).startswith("2026-09-02T10:00")
    assert norm_date({"created": 1788307200}).startswith("2026-09-02")
    assert norm_date({}) is None


def test_sync_failure_keeps_cursor(client, db):
    from app.services.sync import get_state, sync_integration

    t = make_tenant(db, slug=f"sf-{uuid.uuid4().hex[:6]}")
    row = _keyed(db, t)
    import app.integrations.marketplace as mp
    mp.PromAdapter.pull_orders = lambda self, **kw: {"ok": False, "error": "429 rate limited"}
    try:
        out = sync_integration(db, row.id)
    finally:
        del mp.PromAdapter.pull_orders
    assert out["ok"] is False
    db.refresh(row)
    assert row.status == "error" and "429" in (row.last_error or "")
    assert get_state(db, row).last_success_at is None


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
