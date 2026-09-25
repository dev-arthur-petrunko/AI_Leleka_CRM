"""CRUD подключений + тестові виклики адаптерів.

Ключі зберігаємо в integrations.credentials (потім — Fernet-шифр).
Прод: credentials шифрувати ДО insert (cryptography.Fernet).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_tenant, get_current_user
from app.db.session import get_db
from app.integrations.checkbox import CheckboxAdapter
from app.integrations.marketplace import PromAdapter, RozetkaAdapter, normalize_order
from app.integrations.novaposhta import NovaPoshtaAdapter
from app.integrations.payments import LiqPayAdapter, MonoAdapter
from app.models import Client, Deal, Integration, User

router = APIRouter(prefix="/integrations", tags=["integrations"])

ADAPTERS = {"novaposhta": NovaPoshtaAdapter, "checkbox": CheckboxAdapter,
            "liqpay": LiqPayAdapter, "monobank": MonoAdapter,
            "prom": PromAdapter, "rozetka": RozetkaAdapter}


class IntegrationIn(BaseModel):
    provider: str
    credentials: dict = {}
    settings: dict = {}


@router.get("")
def list_all(tenant_id: UUID = Depends(get_current_tenant),
             db: Session = Depends(get_db)):
    rows = db.query(Integration).filter(Integration.tenant_id == tenant_id).all()
    # ключі НЕ повертаємо (тільки факт наявності) — безпека
    return [{"provider": r.provider, "is_active": r.is_active,
             "has_key": bool(r.credentials),
             "last_sync_at": r.last_sync_at} for r in rows]


@router.post("")
def upsert(data: IntegrationIn, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    if data.provider not in ADAPTERS:
        raise HTTPException(400, f"Unknown provider. Available: {list(ADAPTERS)}")
    row = db.query(Integration).filter(
        Integration.tenant_id == user.tenant_id,
        Integration.provider == data.provider).first()
    if row:
        row.credentials = data.credentials
        row.settings = data.settings
        row.is_active = True
    else:
        row = Integration(tenant_id=user.tenant_id, provider=data.provider,
                          credentials=data.credentials, settings=data.settings)
        db.add(row)
    db.commit()
    return {"ok": True, "provider": data.provider, "has_key": bool(data.credentials)}


@router.post("/{provider}/test")
def test_provider(provider: str, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """Перевірка підключення: stub якщо ключа нема, реальний ping якщо є."""
    row = db.query(Integration).filter(
        Integration.tenant_id == user.tenant_id,
        Integration.provider == provider).first()
    if not row:
        raise HTTPException(404, "Підключіть провайдера через POST /integrations")
    adapter = ADAPTERS[provider](row.credentials, row.settings)
    if provider == "novaposhta":
        return adapter.create_ttn("+380000000000", "Київ", cod=0)
    if provider == "checkbox":
        return adapter.fiscal_receipt(1.0)
    if provider == "liqpay":
        return adapter.invoice_link(1.0, "test-1")
    if provider == "monobank":
        return adapter.create_invoice(1.0)
    return adapter.pull_orders(limit=1) if hasattr(adapter, "pull_orders") else {"ok": True}


@router.post("/{provider}/import-orders")
def import_orders(provider: str, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """Імпорт замовлень -> clients + deals (new_lead тригер спрацює через /clients логіку)."""
    if provider not in ("prom", "rozetka"):
        raise HTTPException(400, "import-orders тільки для prom/rozetka")
    row = db.query(Integration).filter(
        Integration.tenant_id == user.tenant_id,
        Integration.provider == provider).first()
    if not row:
        raise HTTPException(404, "Підключіть провайдера")
    adapter = ADAPTERS[provider](row.credentials, row.settings)
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
