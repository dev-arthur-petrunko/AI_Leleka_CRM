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
        n_products = db.query(Product).filter(
            Product.tenant_id == tenant_id,
            Product.sources.has_key(str(r.id))).count() if hasattr(Product.sources, "has_key") else None
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
                  limit: int = Query(50, le=200), offset: int = Query(0, ge=0)):
    query = db.query(Product).filter(Product.tenant_id == tenant_id)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Product.name.ilike(like), Product.sku.ilike(like),
                                 Product.brand.ilike(like)))
    total = query.count()
    return {"total": total, "items": query.order_by(Product.updated_at.desc())
            .limit(limit).offset(offset).all()}


@router.get("/export.xml")
def export_feed(tenant_id: UUID = Depends(get_current_tenant),
                db: Session = Depends(get_db)):
    """Публічний формат обʼєднаного фіда для Prom/Rozetka (прод: за токеном у query)."""
    xml = build_export_yml(db, tenant_id)
    return Response(content=xml, media_type="application/xml",
                    headers={"Content-Disposition": "attachment; filename=leleka-feed.xml"})
