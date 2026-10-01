# -*- coding: utf-8 -*-
"""Фаза 2: телефони, ідемпотентність імпорту, ізоляція замовлень."""

import uuid

import pytest

from app.core.phones import normalize_phone
from tests.conftest import auth_headers, make_tenant, make_user


@pytest.mark.parametrize("raw,expected", [
    ("0501234567", "+380501234567"),
    ("380501234567", "+380501234567"),
    ("+38 (050) 123-45-67", "+380501234567"),
    ("050 123 45 67", "+380501234567"),
    ("501234567", "+380501234567"),
    ("00380501234567", "+380501234567"),
    ("мусор", None),
    ("", None),
    (None, None),
    ("123", None),
])
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


def _dto(i=1):
    return {"source": "prom", "external_id": f"ord-{i}",
            "client_name": "Іван", "phone": "0501234567",
            "total": 100.0 * i, "order_number": f"A-{i}",
            "items": [{"sku": "SKU1", "name": "Товар", "qty": 2, "unit_price": 50}]}


def test_double_import_same_count(client, db):
    from app.services.orders import upsert_order

    t = make_tenant(db, slug=f"shop-{uuid.uuid4().hex[:6]}")
    u = make_user(db, t, role="owner")
    h = auth_headers(u)
    for _ in range(2):
        for i in (1, 2):
            upsert_order(db, t.id, _dto(i), origin="import")
    r = client.get("/orders", headers=h).json()
    assert r["total"] == 2
    r = client.get("/orders?status=new", headers=h).json()
    assert r["total"] == 2
    # позиції пересинхронізовано, не подвоєно
    oid = r["items"][0]["id"]
    detail = client.get(f"/orders/{oid}", headers=h).json()
    assert len(detail["items"]) == 1
    assert len(detail["history"]) >= 1


def test_orders_isolated_and_rbac(client, db):
    ta = make_tenant(db, slug=f"oa-{uuid.uuid4().hex[:6]}")
    tb = make_tenant(db, slug=f"ob-{uuid.uuid4().hex[:6]}")
    ua = make_user(db, ta, role="owner")
    ub = make_user(db, tb, role="viewer")
    ha, hb = auth_headers(ua), auth_headers(ub)
    r = client.post("/orders", headers=ha, json={
        "source": "manual", "external_id": "m1", "client_name": "К",
        "total": 50})
    assert r.status_code == 200
    oid = r.json()["id"]
    assert client.get(f"/orders/{oid}", headers=hb).status_code == 404
    assert client.post("/orders", headers=hb, json={
        "source": "manual", "external_id": "m2"}).status_code == 403


def test_tags_pipelines(client, db):
    t = make_tenant(db, slug=f"tp-{uuid.uuid4().hex[:6]}")
    u = make_user(db, t, role="manager")
    h = auth_headers(u)
    assert client.post("/orders/tags/attach", headers=h,
                       json={"name": "vip", "entity_type": "client",
                             "entity_id": "x"}).status_code == 200
    assert client.get("/orders/tags/all", headers=h).json()[0]["name"] == "vip"
    assert client.post("/orders/custom-fields", headers=h,
                       json={"entity": "client", "key": "np_city",
                             "label": "Місто НП"}).status_code == 200
    pipes = client.get("/orders/pipelines", headers=h).json()
    assert pipes[0]["stages"]  # дефолтна воронка з 5 стадій
