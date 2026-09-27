"""Надсилання персоналізованих листів клієнту: email / telegram / viber.

Текст генерує AI (тільки з назви товару — без PII, див. services/messaging.py),
ім'я клієнта та номер замовлення підставляються локально.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.core.security import decrypt_credentials
from app.db.session import get_db
from app.integrations.email import SmtpEmailAdapter
from app.integrations.telegram import TelegramAdapter
from app.integrations.viber import ViberAdapter
from app.models import Client, Deal, Integration, Interaction, User
from app.services.messaging import SUPPORTED_CHANNELS, compose_message

router = APIRouter(prefix="/clients", tags=["messages"])
_writer = require_role("owner", "admin", "manager")

ADAPTERS = {"email": SmtpEmailAdapter, "telegram": TelegramAdapter, "viber": ViberAdapter}
# Яке поле клієнта каналу потрібне, щоб узагалі було кому писати
TARGET_FIELD = {"email": "email", "telegram": "telegram_chat_id", "viber": "viber_id"}


class MessageIn(BaseModel):
    channel: str
    deal_id: str | None = None
    subject: str | None = None  # тільки для email; ігнорується для telegram/viber


@router.post("/{client_id}/message")
def send_message(client_id: str, data: MessageIn,
                 user: User = Depends(_writer), db: Session = Depends(get_db)):
    if data.channel not in SUPPORTED_CHANNELS:
        raise HTTPException(400, f"Канал має бути одним із: {', '.join(SUPPORTED_CHANNELS)}")

    client = db.query(Client).filter(
        Client.id == client_id, Client.tenant_id == user.tenant_id).first()
    if not client:
        raise HTTPException(404, "Клієнта не знайдено")

    deal = None
    if data.deal_id:
        deal = db.query(Deal).filter(
            Deal.id == data.deal_id, Deal.tenant_id == user.tenant_id).first()
        if not deal:
            raise HTTPException(404, "Угоду не знайдено")

    target = getattr(client, TARGET_FIELD[data.channel])
    if not target:
        # Чесна помилка замість тихого "нічого не сталось" —
        # особливо важливо для telegram/viber, де це НЕ рідкість
        # (клієнт міг ще не написати боту першим).
        raise HTTPException(
            422, f"У клієнта немає {TARGET_FIELD[data.channel]} — "
                f"надіслати через {data.channel} неможливо")

    composed = compose_message(client, deal, data.channel)

    row = db.query(Integration).filter(
        Integration.tenant_id == user.tenant_id, Integration.provider == data.channel).first()
    creds = decrypt_credentials(row.credentials) if row and row.credentials else {}
    adapter = ADAPTERS[data.channel](creds)

    if data.channel == "email":
        result = adapter.send_email(target, data.subject or "Дякуємо за замовлення!", composed["text"])
    else:
        result = adapter.send_message(target, composed["text"])

    db.add(Interaction(tenant_id=user.tenant_id, client_id=client.id,
                       deal_id=deal.id if deal else None, author_id=user.id,
                       channel=data.channel, body=composed["text"]))
    db.commit()

    return {"ok": result.get("ok", True), "stub": result.get("stub", False),
           "text": composed["text"], "ai_used": composed["ai_used"],
           "missing_data": composed["missing"], "delivery": result}
