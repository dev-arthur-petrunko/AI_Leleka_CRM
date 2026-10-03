"""Feed Hub API: джерела, запуски, товари, експорт."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.core.deps import get_current_tenant, require_role
from app.core.security import decrypt_credentials, encrypt_credentials
from app.db.session import get_db
from app.models import FeedRun, FeedSource, Product, User
from app.services.feedhub import build_export_yml, run_source

_admin = require_role("owner", "admin")
_writer = require_role("owner", "admin", "manager")

router = APIRouter(prefix="/feedhub", tags=["feedhub"])


class SourceIn(BaseModel):
    name: str
    url: str
    auth: dict = {}  # {type: basic/token, login, password, token} — шифрується
    format: str = "auto"
    interval_minutes: int = 60
    priority: int = 0
    settings: dict = {}  # markup_pct, rounding, exclude_*, hide_zero_stock, field_map


@router.get("/sources")
def list_sources(tenant_id: UUID = Depends(get_current_tenant),
                 db: Session = Depends(get_db)):
    rows = db.query(FeedSource).filter(FeedSource.tenant_id == tenant_id).all()
    out = []
    for r in rows:
        out.append({"id": str(r.id), "name": r.name, "url": r.url,
                    "format": r.format, "interval_minutes": r.interval_minutes,
                    "priority": r.priority, "is_active": r.is_active,
                    "has_auth": bool(r.auth), "last_run_at": r.last_run_at,
                    "last_status": r.last_status})
    return out


@router.post("/sources")
def upsert_source(data: SourceIn, user: User = Depends(_admin),
                  db: Session = Depends(get_db)):
    if data.format not in ("auto", "yml", "google", "facebook", "custom"):
        raise HTTPException(400, "Unknown format")
    if data.interval_minutes not in (15, 60, 1440):
        raise HTTPException(400, "interval must be 15/60/1440")
    enc = encrypt_credentials(data.auth) if data.auth else {}
    row = FeedSource(tenant_id=user.tenant_id, name=data.name, url=data.url,
                     auth=enc, format=data.format,
                     interval_minutes=data.interval_minutes,
                     priority=data.priority, settings=data.settings)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"ok": True, "id": str(row.id)}


@router.delete("/sources/{source_id}")
def delete_source(source_id: UUID, user: User = Depends(_admin),
                  db: Session = Depends(get_db)):
    row = db.query(FeedSource).filter(
        FeedSource.id == source_id, FeedSource.tenant_id == user.tenant_id).first()
    if not row:
        raise HTTPException(404, "Not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.post("/sources/{source_id}/run")
def run_now(source_id: UUID, user: User = Depends(_writer),
            db: Session = Depends(get_db)):
    """«Оновити зараз» — поза розкладом."""
    row = db.query(FeedSource).filter(
        FeedSource.id == source_id, FeedSource.tenant_id == user.tenant_id).first()
    if not row:
        raise HTTPException(404, "Not found")
    return run_source(db, row.id)


@router.get("/runs")
def list_runs(tenant_id: UUID = Depends(get_current_tenant),
              db: Session = Depends(get_db),
              source_id: UUID | None = Query(None), limit: int = Query(30, le=100)):
    q = db.query(FeedRun).filter(FeedRun.tenant_id == tenant_id)
    if source_id:
        q = q.filter(FeedRun.source_id == source_id)
    return q.order_by(FeedRun.started_at.desc()).limit(limit).all()


@router.get("/products")
def list_products(tenant_id: UUID = Depends(get_current_tenant),
                  db: Session = Depends(get_db),
                  q: str | None = Query(None),
                  category: str | None = Query(None),
                  in_stock: bool | None = Query(None),
                  limit: int = Query(50, le=200), offset: int = Query(0, ge=0)):
    query = db.query(Product).filter(Product.tenant_id == tenant_id)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Product.name.ilike(like), Product.sku.ilike(like),
                                 Product.brand.ilike(like)))
    if category:
        query = query.filter(Product.category == category)
    if in_stock is True:
        query = query.filter(Product.stock > 0)
    elif in_stock is False:
        query = query.filter(Product.stock <= 0)
    total = query.count()
    return {"total": total, "items": query.order_by(Product.updated_at.desc())
            .limit(limit).offset(offset).all()}


class MappingIn(BaseModel):
    xml_path: str
    crm_field: str
    transform: dict = {}


@router.get("/sources/{source_id}/preview")
def preview_source(source_id: UUID, user: User = Depends(_writer),
                   db: Session = Depends(get_db)):
    """Перші 20 товарів + запропонований маппинг (майстер додавання)."""
    from app.models import FeedMapping
    from app.services.feedhub import detect_format, fetch_feed, parse_offers

    row = db.query(FeedSource).filter(
        FeedSource.id == source_id, FeedSource.tenant_id == user.tenant_id).first()
    if not row:
        raise HTTPException(404, "Not found")
    auth = decrypt_credentials(row.auth) if row.auth else {}
    fetched = fetch_feed(row, auth)
    if fetched.get("skipped"):
        return {"skipped": True, "reason": fetched.get("reason")}
    fmt = row.format if row.format != "auto" else detect_format(fetched["content"])
    offers = parse_offers(fetched["content"], fmt)[:20]
    saved = db.query(FeedMapping).filter(
        FeedMapping.source_id == row.id).all()
    mapping = ([{"xml_path": m.xml_path, "crm_field": m.crm_field,
                 "transform": m.transform} for m in saved]
               or [{"xml_path": k, "crm_field": k, "transform": {}}
                   for k in ("sku", "name", "price", "stock", "brand", "category")])
    return {"format": fmt, "count_preview": len(offers), "offers": offers, "mapping": mapping}


@router.put("/sources/{source_id}/mapping")
def save_mapping(source_id: UUID, items: list[MappingIn],
                 user: User = Depends(_admin), db: Session = Depends(get_db)):
    """Зберегти візуальний маппинг «тег XML → поле CRM»."""
    from app.models import FeedMapping

    row = db.query(FeedSource).filter(
        FeedSource.id == source_id, FeedSource.tenant_id == user.tenant_id).first()
    if not row:
        raise HTTPException(404, "Not found")
    db.query(FeedMapping).filter(FeedMapping.source_id == row.id).delete()
    for it in items:
        db.add(FeedMapping(tenant_id=user.tenant_id, source_id=row.id,
                           xml_path=it.xml_path, crm_field=it.crm_field,
                           transform=it.transform))
    db.commit()
    return {"ok": True, "saved": len(items)}


class MergeRulesIn(BaseModel):
    rules: list[dict] = []  # [{field, strategy, source_order}]


@router.get("/merge-rules")
def get_merge_rules(tenant_id: UUID = Depends(get_current_tenant),
                    db: Session = Depends(get_db)):
    from app.models import MergeRule

    return [{"field": r.field, "strategy": r.strategy,
             "source_order": r.source_order}
            for r in db.query(MergeRule).filter(
                MergeRule.tenant_id == tenant_id).all()]


@router.put("/merge-rules")
def put_merge_rules(data: MergeRulesIn, user: User = Depends(_admin),
                    db: Session = Depends(get_db)):
    """Правила конфліктів: [{field: price, strategy: min|... , source_order: [uuid...]}]."""
    from app.models import MergeRule

    allowed = {"source_priority", "min", "max", "latest"}
    db.query(MergeRule).filter(MergeRule.tenant_id == user.tenant_id).delete()
    for r in data.rules:
        if r.get("strategy") not in allowed or not r.get("field"):
            raise HTTPException(400, "strategy: source_priority/min/max/latest; field обовʼязкове")
        db.add(MergeRule(tenant_id=user.tenant_id, field=r["field"],
                         strategy=r["strategy"], source_order=r.get("source_order") or []))
    db.commit()
    return {"ok": True, "saved": len(data.rules)}


@router.get("/export.xml")
def export_feed(tenant_id: UUID = Depends(get_current_tenant),
                db: Session = Depends(get_db)):
    """Публічний формат обʼєднаного фіда для Prom/Rozetka (прод: за токеном у query)."""
    xml = build_export_yml(db, tenant_id)
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": "attachment; filename=leleka-feed.xml"})
