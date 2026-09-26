"""CRUD підключень + тестові виклики адаптерів.

Безпека:
- ключі в БД — ТІЛЬКИ Fernet-шифровані (encrypt_credentials ДО insert);
- GET ніколи не повертає ключі;
- весь роутер — owner/admin + відповідна платна фіча за провайдером.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_tenant, require_plan_feature, require_role
from app.core.security import decrypt_credentials, encrypt_credentials
from app.db.session import get_db
from app.integrations.checkbox import CheckboxAdapter
from app.integrations.marketplace import PromAdapter, RozetkaAdapter, normalize_order
from app.integrations.novaposhta import NovaPoshtaAdapter
from app.integrations.payments import LiqPayAdapter, MonoAdapter
from app.integrations.sms import SendPulseAdapter, TurboSmsAdapter
from app.models import Client, Deal, Integration, Tenant, User
from app.services.billing import current_plan

_admin = require_role("owner", "admin")

router = APIRouter(prefix="/integrations", tags=["integrations"])

ADAPTERS = {"novaposhta": NovaPoshtaAdapter, "checkbox": CheckboxAdapter,
            "liqpay": LiqPayAdapter, "monobank": MonoAdapter,
            "prom": PromAdapter, "rozetka": RozetkaAdapter,
            "sendpulse": SendPulseAdapter, "turbosms": TurboSmsAdapter}

# Яка платна фіча потрібна для провайдера (Free — жодної)
PROVIDER_FEATURE = {"prom": "marketplace", "rozetka": "marketplace",
                    "novaposhta": "novaposhta", "checkbox": "fiscal",
                    "sendpulse": "marketplace", "turbosms": "marketplace"}


class IntegrationIn(BaseModel):
    provider: str
    credentials: dict = {}
    settings: dict = {}


def _gate(user: User, db: Session, provider: str):
    feature = PROVIDER_FEATURE.get(provider)
    if feature:
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if feature not in current_plan(tenant)["features"]:
            raise HTTPException(402, f"Провайдер '{provider}' потребує тариф із фічею '{feature}'")


@router.get("")
def list_all(tenant_id: UUID = Depends(get_current_tenant),
             user: User = Depends(_admin),
             db: Session = Depends(get_db)):
    rows = db.query(Integration).filter(Integration.tenant_id == tenant_id).all()
    # ключі НЕ повертаємо (тільки факт наявності)
    return [{"provider": r.provider, "is_active": r.is_active,
             "has_key": bool(r.credentials),
             "last_sync_at": r.last_sync_at} for r in rows]


@router.post("")
def upsert(data: IntegrationIn, user: User = Depends(_admin),
           db: Session = Depends(get_db)):
    if data.provider not in ADAPTERS:
        raise HTTPException(400, f"Unknown provider. Available: {list(ADAPTERS)}")
    _gate(user, db, data.provider)
    enc = encrypt_credentials(data.credentials) if data.credentials else {}
    row = db.query(Integration).filter(
        Integration.tenant_id == user.tenant_id,
        Integration.provider == data.provider).first()
    if row:
        row.credentials = enc
        row.settings = data.settings
        row.is_active = True
    else:
        row = Integration(tenant_id=user.tenant_id, provider=data.provider,
                          credentials=enc, settings=data.settings)
        db.add(row)
    db.commit()
    return {"ok": True, "provider": data.provider, "has_key": bool(data.credentials)}


@router.post("/{provider}/test")
def test_provider(provider: str, user: User = Depends(_admin),
                  db: Session = Depends(get_db)):
    """Перевірка підключення: stub якщо ключа нема, реальний ping якщо є."""
    if provider not in ADAPTERS:
        raise HTTPException(400, "Unknown provider")
    _gate(user, db, provider)
    row = db.query(Integration).filter(
        Integration.tenant_id == user.tenant_id,
        Integration.provider == provider).first()
    if not row:
        raise HTTPException(404, "Підключіть провайдера через POST /integrations")
    creds = decrypt_credentials(row.credentials)
    adapter = ADAPTERS[provider](creds, row.settings)
    if provider == "novaposhta":
        return adapter.create_ttn("+380000000000", "Київ", cod=0)
    if provider == "checkbox":
        return adapter.fiscal_receipt(1.0)
    if provider == "liqpay":
        return adapter.invoice_link(1.0, "test-1")
    if provider == "monobank":
        return adapter.create_invoice(1.0)
    if provider in ("sendpulse", "turbosms"):
        return adapter.send_sms("+380000000000", "Leleka test")
    return adapter.pull_orders(limit=1) if hasattr(adapter, "pull_orders") else {"ok": True}


@router.post("/{provider}/import-orders")
def import_orders(provider: str, user: User = Depends(_admin),
                  db: Session = Depends(get_db)):
    """Імпорт замовлень -> clients + deals."""
    if provider not in ("prom", "rozetka"):
        raise HTTPException(400, "import-orders тільки для prom/rozetka")
    _gate(user, db, provider)
    row = db.query(Integration).filter(
        Integration.tenant_id == user.tenant_id,
        Integration.provider == provider).first()
    if not row:
        raise HTTPException(404, "Підключіть провайдера")
    creds = decrypt_credentials(row.credentials)
    adapter = ADAPTERS[provider](creds, row.settings)
    resp = adapter.pull_orders()
    if resp.get("stub"):
        return resp  # без ключа — чесний stub
    orders = resp.get("data", {}).get("orders", []) if isinstance(resp.get("data"), dict) else []
    created = 0
    for raw in orders[:50]:
        o = normalize_order(provider, raw)
        exists = db.query(Client).filter(
            Client.tenant_id == user.tenant_id, Client.phone == o["phone"]).first() if o["phone"] else None
        client = exists or Client(tenant_id=user.tenant_id, name=o["name"],
                                  phone=o["phone"], source=provider)
        if not exists:
            db.add(client)
            db.flush()
        db.add(Deal(tenant_id=user.tenant_id, client_id=client.id,
                    title=f"Замовлення {provider} #{o['external_id']}",
                    amount=o["amount"], stage="new", manager_id=user.id))
        created += 1
    from datetime import datetime, timezone
    row.last_sync_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "imported": created}
