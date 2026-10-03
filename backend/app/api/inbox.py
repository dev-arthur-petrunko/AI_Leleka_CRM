"""Inbox (фаза 5): діалоги, відповіді, шаблони, вхідний Telegram-вебхук."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_tenant, require_role
from app.core.rate import limiter
from app.db.session import get_db
from app.models import Client, Conversation, Integration, Message, MessageTemplate, User
from datetime import UTC

_writer = require_role("owner", "admin", "manager")

router = APIRouter(prefix="/inbox", tags=["inbox"])


@router.get("/conversations")
def list_conv(tenant_id: UUID = Depends(get_current_tenant),
              db: Session = Depends(get_db),
              status: str | None = Query(None),
              limit: int = Query(50, le=200)):
    q = db.query(Conversation).filter(Conversation.tenant_id == tenant_id)
    if status:
        q = q.filter(Conversation.status == status)
    return q.order_by(Conversation.last_message_at.desc().nullslast()).limit(limit).all()


@router.get("/conversations/{cid}")
def get_conv(cid: UUID, tenant_id: UUID = Depends(get_current_tenant),
             db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(
        Conversation.id == cid, Conversation.tenant_id == tenant_id).first()
    if not conv:
        raise HTTPException(404, "Not found")
    msgs = db.query(Message).filter(Message.conversation_id == cid)\
        .order_by(Message.created_at).limit(200).all()
    return {"conversation": conv, "messages": msgs}


class AssignIn(BaseModel):
    assignee_id: UUID | None = None
    status: str | None = None


@router.patch("/conversations/{cid}")
def patch_conv(cid: UUID, data: AssignIn, user: User = Depends(_writer),
               db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(
        Conversation.id == cid, Conversation.tenant_id == user.tenant_id).first()
    if not conv:
        raise HTTPException(404, "Not found")
    if data.assignee_id is not None:
        conv.assignee_id = data.assignee_id
    if data.status in ("open", "closed"):
        conv.status = data.status
    db.commit()
    return conv


class ReplyIn(BaseModel):
    body: str


@router.post("/conversations/{cid}/reply")
def reply(cid: UUID, data: ReplyIn, user: User = Depends(_writer),
           db: Session = Depends(get_db)):
    """Відповідь менеджеру прямо з CRM (поки Telegram; Viber/Meta — за тим самим патерном)."""
    from datetime import datetime

    from app.core.security import decrypt_credentials

    conv = db.query(Conversation).filter(
        Conversation.id == cid, Conversation.tenant_id == user.tenant_id).first()
    if not conv:
        raise HTTPException(404, "Not found")
    sent: dict = {"ok": True, "stub": True}
    if conv.channel == "telegram":
        from app.integrations.telegram import TelegramAdapter

        row = db.query(Integration).filter(
            Integration.tenant_id == user.tenant_id,
            Integration.provider == "telegram").first()
        client = db.query(Client).filter(Client.id == conv.client_id).first()
        target = (client.telegram_chat_id or "") if client else ""
        creds = decrypt_credentials(row.credentials) if row and row.credentials else {}
        sent = TelegramAdapter(creds, row.settings if row else {}).send_message(target, data.body)
    msg = Message(tenant_id=user.tenant_id, conversation_id=cid, direction="out",
                  channel=conv.channel, body=data.body,
                  status="sent" if sent.get("ok") and not sent.get("stub") else "queued")
    db.add(msg)
    conv.last_message_at = datetime.now(UTC)
    db.commit()
    return {"ok": True, "delivery": sent}


class TemplateIn(BaseModel):
    name: str
    channel: str
    body: str


@router.get("/templates")
def list_tpl(tenant_id: UUID = Depends(get_current_tenant),
             db: Session = Depends(get_db)):
    return db.query(MessageTemplate).filter(
        MessageTemplate.tenant_id == tenant_id).all()


@router.post("/templates")
def create_tpl(data: TemplateIn, user: User = Depends(_writer),
               db: Session = Depends(get_db)):
    row = MessageTemplate(tenant_id=user.tenant_id, **data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def render_template(body: str, client=None, order=None, shipment=None) -> str:
    """Підстановки {{client.first_name}} {{order.number}} {{shipment.ttn}}."""
    out = body
    if client:
        out = out.replace("{{client.first_name}}", client.first_name or client.name or "")
    if order:
        out = out.replace("{{order.number}}", order.order_number or str(order.external_id))
    if shipment:
        out = out.replace("{{shipment.ttn}}", shipment.ttn or "")
    return out


@router.post("/webhooks/telegram")
@limiter.limit("120/minute")
async def telegram_incoming(request: Request, db: Session = Depends(get_db)):
    """Вхідні повідомлення бота: secret_token з налаштувань вебхука Telegram."""
    import os
    from datetime import datetime

    from app.services.orders import find_or_create_client

    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    expected = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    if not expected or secret != expected:
        raise HTTPException(401, "Bad secret")
    update = await request.json()
    msg = (update.get("message") or update.get("edited_message") or {})
    chat = msg.get("chat") or {}
    chat_id, text = str(chat.get("id", "")), (msg.get("text") or "")[:2000]
    msg_id = str(msg.get("message_id", ""))
    if not chat_id or not text:
        return {"ok": True, "skipped": True}
    # tenant — за ботом: шукаємо інтеграцію telegram з таким... MVP: перший активний
    # (прод: мапити bot_token → tenant через integrations.credentials)
    from app.models import Integration

    row = db.query(Integration).filter(
        Integration.provider == "telegram", Integration.is_active.is_(True)).first()
    if not row:
        return {"ok": True, "skipped": True, "reason": "no tenant bot"}
    client = db.query(Client).filter(
        Client.tenant_id == row.tenant_id,
        Client.telegram_chat_id == chat_id).first()
    if not client:
        name = ((msg.get("from") or {}).get("first_name", "") or "Telegram-лід").strip()
        client = find_or_create_client(db, row.tenant_id, name,
                                       source="telegram")
        client.telegram_chat_id = chat_id
        db.commit()
    conv = db.query(Conversation).filter(
        Conversation.tenant_id == row.tenant_id, Conversation.client_id == client.id,
        Conversation.channel == "telegram", Conversation.status == "open").first()
    if not conv:
        conv = Conversation(tenant_id=row.tenant_id, client_id=client.id,
                            channel="telegram")
        db.add(conv)
        db.flush()
    exists = db.query(Message).filter(
        Message.conversation_id == conv.id, Message.external_id == msg_id).first()
    if not exists:
        db.add(Message(tenant_id=row.tenant_id, conversation_id=conv.id,
                       direction="in", channel="telegram", body=text,
                       external_id=msg_id, status="delivered"))
    conv.last_message_at = datetime.now(UTC)
    db.commit()
    return {"ok": True}
