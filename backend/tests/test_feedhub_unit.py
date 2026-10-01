"""Feed Hub: чисті unit-тести без БД (ТЗ 1.6).

- парсинг YML і Google-фіда
- склейка: стратегії min/max/source_priority/latest (чиста функція _pick_value)
- 304-скіп (через мок requests)
- SSRF-блок (loopback, приватні, file://)
- XXE-файл відхилено
DB-тести (bulk, merge end-to-end) — окремо з testcontainers, тут їх нема.
"""

from unittest.mock import patch

import pytest
from app.services.feedhub import (
    _guard_url,
    _pick_value,
    detect_format,
    fetch_feed,
    parse_offers,
)

YML = (
    b"<?xml version='1.0'?><yml_catalog><shop><offers>"
    b"<offer id='1' available='true'><name>Test</name><vendorCode>SKU1</vendorCode>"
    b"<price>100</price><currencyId>UAH</currencyId><categoryId>5</categoryId>"
    b"<quantity>3</quantity><vendor>Acme</vendor></offer>"
    b"</offers></shop></yml_catalog>"
)
GOO = (
    b"<rss><channel><item>"
    b"<g:id xmlns:g='http://base.google.com/ns/1.0'>A1</g:id>"
    b"<title>Phone</title>"
    b"<g:price xmlns:g='http://base.google.com/ns/1.0'>250 USD</g:price>"
    b"<g:availability xmlns:g='http://base.google.com/ns/1.0'>in_stock</g:availability>"
    b"</item></channel></rss>"
)
XXE = (
    b"<?xml version='1.0'?><!DOCTYPE r [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]>"
    b"<yml_catalog><shop><offers><offer id='1'><name>&xxe;</name>"
    b"<vendorCode>X</vendorCode><price>1</price></offer></offers></shop></yml_catalog>"
)


class FakeSource:
    url = "https://example.com/feed.xml"
    settings = {}
    last_etag = None
    last_modified = None
    last_hash = None


def test_detect():
    assert detect_format(YML) == "yml"
    assert detect_format(GOO) == "google"


def test_parse_yml():
    (o,) = parse_offers(YML, "yml")
    assert o["sku"] == "SKU1" and o["price"] == 100.0 and o["stock"] == 3
    assert o["brand"] == "Acme"


def test_parse_google():
    (o,) = parse_offers(GOO, "google")
    assert o["sku"] == "A1" and o["currency"] == "USD" and o["stock"] == 100


def test_strategies():
    rules = {"price": {"strategy": "min"}, "stock": {"strategy": "max"}}
    assert _pick_value("price", 100, "a", 90, "b", rules, {}) == (90, "b")
    assert _pick_value("stock", 3, "a", 9, "b", rules, {}) == (9, "b")
    assert _pick_value("name", "Old", "a", "New", "b",
                       {"name": {"strategy": "latest"}}, {}) == ("New", "b")
    prio = {"name": {"strategy": "source_priority", "order": ["b", "a"]}}
    assert _pick_value("name", "Old", "a", "New", "b", prio, {}) == ("New", "b")


def test_304_skip():
    class Resp:
        status_code = 304
        headers = {}

    with patch("app.services.feedhub.requests.Session") as Sess:
        Sess.return_value.get.return_value = Resp()
        out = fetch_feed(FakeSource(), {})
    assert out["skipped"] is True and out["reason"] == "not-modified-etag"


@pytest.mark.parametrize("url", [
    "http://localhost:8000/x",
    "http://127.0.0.1/x",
    "http://10.0.0.5/x",
    "http://172.16.9.9/x",
    "http://192.168.1.2/x",
    "http://169.254.169.254/x",
    "file:///etc/passwd",
    "ftp://example.com/x",
])
def test_ssrf_blocked(url):
    with pytest.raises(ValueError):
        _guard_url(url)


def test_xxe_rejected():
    from defusedxml.common import EntitiesForbidden

    with pytest.raises(EntitiesForbidden):
        parse_offers(XXE, "yml")
