"""CRUD клієнтів: tenant-ізоляція + audit_log + пошук/фільтри + CSV-імпорт + interactions."""

import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import get_current_tenant, require_role
from app.db.session import get_db
from app.models import AuditLog, Client, Interaction, User
from app.schemas import ClientIn

_writer = require_role("owner", "admin", "manager")

router = APIRouter(prefix="/clients", tags=["clients"])


class InteractionIn(BaseModel):
    channel: str = "note"  # call/sms/email/meeting/note
    body: str = ""
    deal_id: UUID | None = None


def _audit(db: Session, user: User, entity_id: str, action: str,
           old=None, new=None, request: Request | None = None):
    db.add(AuditLog(
        tenant_id=user.tenant_id, actor_id=user.id,
        entity_type="client", entity_id=entity_id, action=action,
        old_values=old, new_values=new,
        ip=request.client.host if request else None,
    ))


@router.get("")
def list_clients(tenant_id: UUID = Depends(get_current_tenant),
                 db: Session = Depends(get_db),
                 q: str | None = Query(None, description="Пошук за ім'ям/телефоном/email"),
                 segment: str | None = Query(None, description="new/regular/vip/lost"),
                 limit: int = Query(50, le=200), offset: int = Query(0, ge=0)):
    query = db.query(Client).filter(
        Client.tenant_id == tenant_id, Client.deleted_at.is_(None))
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Client.name.ilike(like), Client.phone.ilike(like),
                                 Client.email.ilike(like)))
    if segment:
        query = query.filter(Client.segment == segment)
    total = query.count()
    rows = query.order_by(Client.created_at.desc()).limit(limit).offset(offset).all()
    return {"total": total, "limit": limit, "offset": offset, "items": rows}


@router.post("")
def create_client(data: ClientIn, request: Request,
                  user: User = Depends(_writer),
                  db: Session = Depends(get_db)):
    c = Client(tenant_id=user.tenant_id, **data.model_dump())
    db.add(c)
    db.flush()
    _audit(db, user, str(c.id), "create", new=data.model_dump(mode="json"), request=request)
    db.flush()
    # Тригер new_lead -> assign_manager / notify
    from app.services.automation import run_automations
    run_automations(db, user.tenant_id, "new_lead", {
        "client_id": str(c.id), "source": c.source,
        "manager_id": str(c.assigned_to) if c.assigned_to else None,
    })
    db.refresh(c)
    return c


MAX_CSV_BYTES = 5 * 1024 * 1024  # 5 МБ вистачає з запасом на кілька тисяч рядків


@router.post("/import-csv")
def import_csv(file: UploadFile = File(...),
               user: User = Depends(_writer),
               db: Session = Depends(get_db)):
    """Імпорт клієнтів з CSV/Excel-експорту. Колонки: name,phone,email,segment."""
    if file.size is not None and file.size > MAX_CSV_BYTES:
        raise HTTPException(413, f"Файл завеликий (>{MAX_CSV_BYTES // 1024 // 1024} МБ)")
    raw = file.file.read(MAX_CSV_BYTES + 1)
    if len(raw) > MAX_CSV_BYTES:
        raise HTTPException(413, f"Файл завеликий (>{MAX_CSV_BYTES // 1024 // 1024} МБ)")
    raw = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    created = 0
    for row in reader:
        name = (row.get("name") or "").strip()
        if not name:
            continue
        seg = (row.get("segment") or "new").strip() or "new"
        if seg not in ("new", "regular", "vip", "lost"):
            seg = "new"
        db.add(Client(tenant_id=user.tenant_id, name=name,
                      phone=(row.get("phone") or "").strip() or None,
                      email=(row.get("email") or "").strip() or None,
                      segment=seg, source="import"))
        created += 1
        if created >= 1000:
            break
    db.commit()
    return {"ok": True, "imported": created}


@router.get("/{client_id}/interactions")
def list_interactions(client_id: UUID,
                      tenant_id: UUID = Depends(get_current_tenant),
                      db: Session = Depends(get_db),
                      limit: int = Query(50, le=200)):
    """Таймлайн комунікацій клієнта — джерело для картки-досьє."""
    return db.query(Interaction).filter(
        Interaction.client_id == client_id, Interaction.tenant_id == tenant_id)\
        .order_by(Interaction.created_at.desc()).limit(limit).all()


@router.post("/{client_id}/interactions")
def add_interaction(client_id: UUID, data: InteractionIn,
                    user: User = Depends(_writer),
                    db: Session = Depends(get_db)):
    c = db.query(Client).filter(
        Client.id == client_id, Client.tenant_id == user.tenant_id).first()
    if not c:
        raise HTTPException(404, "Not found")
    if data.channel not in ("call", "sms", "email", "meeting", "note"):
        raise HTTPException(400, "Unknown channel")
    it = Interaction(tenant_id=user.tenant_id, client_id=client_id,
                     deal_id=data.deal_id, author_id=user.id,
                     channel=data.channel, body=data.body[:5000])
    db.add(it)
    db.commit()
    db.refresh(it)
    return it


@router.delete("/{client_id}")
def delete_client(client_id: UUID, request: Request,
                  user: User = Depends(_writer),
                  db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    c = db.query(Client).filter(
        Client.id == client_id, Client.tenant_id == user.tenant_id
    ).first()
    if not c:
        raise HTTPException(404, "Not found")
    c.deleted_at = datetime.now(timezone.utc)  # soft-delete
    _audit(db, user, str(c.id), "delete", request=request)
    db.commit()
    return {"ok": True}
