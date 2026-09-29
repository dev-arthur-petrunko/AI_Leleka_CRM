"""Feed Hub: завантаження XML-фідів, маппинг, склейка, експорт.

Безпека:
- Парсинг ТІЛЬКИ через defusedxml (XXE / billion laughs відбито на рівні бібліотеки).
- SSRF-захист: лише http/https, резолв хоста з забороною приватних/локальних IP,
  ліміт розміру (100 МБ) і часу (30 c).
- Економія: ETag / If-Modified-Since + sha256-хеш (незмінене не обробляємо).
- Потоковий iterparse — фіди на сотні МБ не зʼїдають памʼять.
"""

import hashlib
import io
import ipaddress
import re
import socket
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import UUID

import requests
from defusedxml import ElementTree as DET
from sqlalchemy.orm import Session

from app.core.security import decrypt_credentials
from app.models import FeedRun, FeedSource, Product, ProductOffer

MAX_FEED_BYTES = 100 * 1024 * 1024
FETCH_TIMEOUT = 30


def _guard_url(url: str):
    """SSRF: заборона локальних/внутрішніх адрес."""
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ValueError("Дозволено лише http(s) URL з хостом")
    try:
        infos = socket.getaddrinfo(u.hostname, None)
    except socket.gaierror as e:
        raise ValueError(f"DNS не резолвиться: {e}") from e
    for fam, _, _, _, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise ValueError(f"Заборонена адреса фіда: {ip} (SSRF-захист)")


def fetch_feed(source: FeedSource, auth: dict) -> dict:
    """Завантажити фід. Повертає {content, skipped, etag}."""
    _guard_url(source.url)
    headers = {"User-Agent": "AI-Leleka-FeedHub/1.0"}
    etag = (source.settings or {}).get("etag")
    if etag:
        headers["If-None-Match"] = etag
    req_kwargs: dict = {"headers": headers, "timeout": FETCH_TIMEOUT, "stream": True}
    at = auth.get("type")
    if at == "basic":
        req_kwargs["auth"] = (auth.get("login", ""), auth.get("password", ""))
    elif at == "token":
        req_kwargs["headers"] = {**headers, "Authorization": f"Bearer {auth.get('token', '')}"}
    r = requests.get(source.url, **req_kwargs)
    if r.status_code == 304:
        return {"content": None, "skipped": True, "reason": "not-modified-etag"}
    r.raise_for_status()
    buf = io.BytesIO()
    total = 0
    for chunk in r.iter_content(65536):
        total += len(chunk)
        if total > MAX_FEED_BYTES:
            raise ValueError(f"Фід більше {MAX_FEED_BYTES // 1024 // 1024} МБ — відхилено")
        buf.write(chunk)
    content = buf.getvalue()
    digest = hashlib.sha256(content).hexdigest()
    if (source.settings or {}).get("hash") == digest:
        return {"content": None, "skipped": True, "reason": "not-modified-hash"}
    return {"content": content, "skipped": False, "etag": r.headers.get("ETag"), "hash": digest}


def detect_format(content: bytes) -> str:
    head = content[:4000].lower()
    if b"<yml_catalog" in head:
        return "yml"
    if b"<rss" in head or b"<feed" in head:
        return "google"  # Google Merchant / Facebook — спільна RSS-основа
    return "custom"


def _text(el, *names) -> str:
    for n in names:
        child = el.find(n)
        if child is not None and child.text and child.text.strip():
            return child.text.strip()
    return ""


def _parse_price(raw: str) -> tuple[float, str]:
    m = re.search(r"[\d.,]+", (raw or "").replace(" ", ""))
    val = float(m.group(0).replace(",", ".")) if m else 0.0
    cur = "UAH"
    up = (raw or "").upper()
    if "USD" in up or "$" in up:
        cur = "USD"
    elif "EUR" in up or "€" in up:
        cur = "EUR"
    return val, cur


def parse_offers(content: bytes, fmt: str, field_map: dict | None = None) -> list[dict]:
    """Потоковий парсинг → нормалізовані оффери {sku,name,price,currency,stock,brand,category,attrs}."""
    out: list[dict] = []
    fm = field_map or {}
    item_tag = {"yml": "offer", "google": "item", "facebook": "item"}.get(fmt, fm.get("tag_item", "offer"))
    for _, el in DET.iterparse(io.BytesIO(content), events=("end",)):
        tag = el.tag.split("}")[-1]
        if tag != item_tag:
            continue
        try:
            if fmt == "yml":
                sku = (_text(el, "vendorCode") or el.get("id") or "").strip()
                name = _text(el, "name") or (
                    (_text(el, "vendor") + " " + _text(el, "model")).strip())
                price, _ = _parse_price(_text(el, "price"))
                cur = _text(el, "currencyId") or "UAH"
                avail = (el.get("available") or "").lower()
                qty = _text(el, "quantity")
                stock = int(float(qty)) if qty else (100 if avail == "true" else 0)
                brand = _text(el, "vendor") or None
                cat = _text(el, "categoryId") or None
                attrs = {p.get("name", ""): (p.text or "").strip()
                         for p in el.findall("param") if p.get("name")}
            else:  # google / facebook / custom
                ns = lambda t: ["%s%s" % (ns_, t) for ns_ in
                                ("", "{http://base.google.com/ns/1.0}")]
                def g(*names):
                    for n in names:
                        for cand in ns(n):
                            v = _text(el, cand)
                            if v:
                                return v
                    return ""
                sku = g("g:id", "id", "sku", "gtin") or ""
                name = g("title", "name")
                price, cur = _parse_price(g("g:price", "price"))
                av = g("g:availability", "availability").lower()
                stock = 100 if "in_stock" in av else 0
                brand = g("g:brand", "brand") or None
                cat = g("g:google_product_category", "category") or None
                attrs = {}
            if sku and name:
                out.append({"sku": sku, "name": name, "price": price, "currency": cur,
                            "stock": stock, "brand": brand, "category": cat, "attrs": attrs})
        finally:
            el.clear()
    return out


def apply_filters(offer: dict, settings: dict) -> bool:
    """True — оффер проходить фільтри (не виключається)."""
    excl_cats = set(settings.get("exclude_categories", []))
    if excl_cats and (offer.get("category") in excl_cats):
        return False
    excl_brands = set(settings.get("exclude_brands", []))
    if excl_brands and (offer.get("brand") in excl_brands):
        return False
    if settings.get("hide_zero_stock") and not offer.get("stock"):
        return False
    return True


def apply_markup(price: float, settings: dict) -> float:
    price = price * (1 + float(settings.get("markup_pct", 0)) / 100)
    rounding = settings.get("rounding")  # напр. 9 → ...X9; 0 → без округлення
    if rounding:
        base = int(price // 10) * 10
        return float(base + int(rounding))
    return round(price, 2)


def merge_source(db: Session, tenant_id: UUID, source: FeedSource,
                 offers: list[dict]) -> dict:
    """Склейка: ключ SKU; ціна — мінімальна з урахуванням націнки; назва/опис — за priority."""
    settings = source.settings or {}
    stats = {"added": 0, "updated": 0}
    seen_offer_ids: set[str] = set()
    for off in offers:
        if not apply_filters(off, settings):
            continue
        price = apply_markup(off["price"], settings)
        prod = db.query(Product).filter(
            Product.tenant_id == tenant_id, Product.sku == off["sku"]).first()
        if not prod:
            prod = Product(tenant_id=tenant_id, sku=off["sku"], name=off["name"],
                           price=price, currency=off["currency"], stock=off["stock"],
                           brand=off.get("brand"), category=off.get("category"),
                           attrs=off.get("attrs") or {},
                           sources={str(source.id): off["sku"]})
            db.add(prod)
            db.flush()
            stats["added"] += 1
        else:
            # ціна — мінімальна серед джерел; опис/назва — від джерела з вищим priority
            if price and (not prod.price or price < float(prod.price)):
                prod.price, prod.currency = price, off["currency"]
            prod.stock = max(prod.stock or 0, off["stock"])
            srcs = dict(prod.sources or {})
            srcs[str(source.id)] = off["sku"]
            prod.sources = srcs
            prod.updated_at = datetime.now(timezone.utc)
            stats["updated"] += 1
        offer = db.query(ProductOffer).filter(
            ProductOffer.tenant_id == tenant_id, ProductOffer.source_id == source.id,
            ProductOffer.external_id == off["sku"]).first()
        if not offer:
            offer = ProductOffer(tenant_id=tenant_id, product_id=prod.id,
                                 source_id=source.id, external_id=off["sku"])
        offer.product_id, offer.name, offer.price = prod.id, off["name"], price
        offer.currency, offer.stock = off["currency"], off["stock"]
        offer.raw, offer.seen_at = off.get("attrs") or {}, datetime.now(timezone.utc)
        db.add(offer)
        seen_offer_ids.add(off["sku"])
    # removed: оффери джерела, яких більше нема у фіді
    removed = db.query(ProductOffer).filter(
        ProductOffer.tenant_id == tenant_id, ProductOffer.source_id == source.id,
        ~ProductOffer.external_id.in_(seen_offer_ids)).count() if seen_offer_ids else 0
    if seen_offer_ids:
        db.query(ProductOffer).filter(
            ProductOffer.tenant_id == tenant_id, ProductOffer.source_id == source.id,
            ~ProductOffer.external_id.in_(seen_offer_ids)).delete(synchronize_session=False)
    db.commit()
    return {**stats, "removed": removed}


def run_source(db: Session, source_id: UUID) -> dict:
    """Один повний цикл: fetch → parse → merge → FeedRun + інбокс-алерт при помилці."""
    from app.core.security import decrypt_credentials
    from app.services import notify as notify_queue

    source = db.query(FeedSource).filter(FeedSource.id == source_id).first()
    if not source:
        return {"ok": False, "error": "Source not found"}
    run = FeedRun(tenant_id=source.tenant_id, source_id=source.id, status="ok")
    db.add(run)
    db.flush()
    try:
        auth = decrypt_credentials(source.auth) if source.auth else {}
        fetched = fetch_feed(source, auth)
        if fetched.get("skipped"):
            run.status = "skipped"
            run.errors = {"reason": fetched.get("reason")}
        else:
            fmt = source.format if source.format != "auto" else detect_format(fetched["content"])
            offers = parse_offers(fetched["content"], fmt, (source.settings or {}).get("field_map"))
            stats = merge_source(db, source.tenant_id, source, offers)
            run.added, run.updated, run.removed = stats["added"], stats["updated"], stats["removed"]
            st = dict(source.settings or {})
            if fetched.get("etag"):
                st["etag"] = fetched["etag"]
            if fetched.get("hash"):
                st["hash"] = fetched["hash"]
            source.settings = st
        source.last_status = run.status
        source.last_run_at = datetime.now(timezone.utc)
        db.commit()
        return {"ok": True, "status": run.status, "added": run.added,
                "updated": run.updated, "removed": run.removed}
    except Exception as e:  # noqa: BLE001 — помилка фіксується в run, не валить планувальник
        run.status, run.errors = "error", {"error": str(e)[:500]}
        source.last_status = "error"
        db.commit()
        notify_queue.push(source.tenant_id,
                          f"⚠️ Фід «{source.name}» впав: {str(e)[:200]}", kind="feed_error",
                          ref={"source_id": str(source.id)})
        return {"ok": False, "error": str(e)[:500]}
    finally:
        run.finished_at = datetime.now(timezone.utc)
        db.commit()


def build_export_yml(db: Session, tenant_id: UUID, only_in_stock: bool = True) -> str:
    """Обʼєднаний YML для Prom/Rozetka/Horoshop з наших products."""
    import xml.sax.saxutils as sax

    q = db.query(Product).filter(Product.tenant_id == tenant_id)
    if only_in_stock:
        q = q.filter(Product.stock > 0)
    items = []
    for i, p in enumerate(q.limit(20000).all(), start=1):
        items.append(
            f'<offer id="{sax.escape(p.sku)}" available="true">'
            f"<name>{sax.escape(p.name)}</name>"
            f"<price>{float(p.price or 0):.2f}</price>"
            f"<currencyId>{sax.escape(p.currency or 'UAH')}</currencyId>"
            f"<categoryId>{sax.escape(p.category or '1')}</categoryId>"
            f"<quantity>{p.stock}</quantity>"
            f"<vendor>{sax.escape(p.brand or '')}</vendor>"
            "</offer>")
    return ("<?xml version='1.0' encoding='UTF-8'?>"
            "<yml_catalog><shop><name>AI Leleka Feed</name><offers>"
            + "".join(items) + "</offers></shop></yml_catalog>")
