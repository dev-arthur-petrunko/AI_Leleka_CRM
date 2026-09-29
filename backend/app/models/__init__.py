"""SQLAlchemy-модели 1-в-1 под db/schema.sql."""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _uuid() -> Mapped[UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


def _now():
    return datetime.utcnow


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[uuid.UUID] = _uuid()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(20), default="free")
    status: Mapped[str] = mapped_column(String(20), default="active")
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Kyiv")
    language: Mapped[str] = mapped_column(String(8), default="uk")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email"),)
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="manager")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


class Client(Base):
    __tablename__ = "clients"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    first_name: Mapped[str | None] = mapped_column(Text)  # для персоналізації листів; може бути відсутнім
    last_name: Mapped[str | None] = mapped_column(Text)   # так само — не всі джерела (маркетплейс) його дають
    phone: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    telegram_chat_id: Mapped[str | None] = mapped_column(Text)  # відомий тільки якщо клієнт написав боту першим
    viber_id: Mapped[str | None] = mapped_column(Text)          # так само — Viber Business не дозволяє писати першим без цього
    source: Mapped[str] = mapped_column(String(20), default="manual")
    segment: Mapped[str] = mapped_column(String(20), default="new")
    notes: Mapped[str] = mapped_column(Text, default="")
    gdpr_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Deal(Base):
    __tablename__ = "deals"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False
    )
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    order_number: Mapped[str | None] = mapped_column(Text)      # зовнішній номер замовлення (маркетплейс), не UUID угоди
    product_summary: Mapped[str | None] = mapped_column(Text)   # що саме купили — для AI-листа; може бути невідомо
    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    currency: Mapped[str] = mapped_column(String(8), default="UAH")
    stage: Mapped[str] = mapped_column(String(20), default="new")
    loss_reason: Mapped[str | None] = mapped_column(Text)
    probability: Mapped[int] = mapped_column(default=0)
    expected_close_date: Mapped[datetime | None] = mapped_column(Date)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now()
    )
    won_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lost_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    deal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE")
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE")
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="open")
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


class Integration(Base):
    __tablename__ = "integrations"
    __table_args__ = (UniqueConstraint("tenant_id", "provider"),)
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    credentials: Mapped[dict] = mapped_column(JSONB, default=dict)  # ENCRYPTED!
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="received")
    retry_count: Mapped[int] = mapped_column(default=0)
    next_retry_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now()
    )
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


class AutomationRule(Base):
    __tablename__ = "automation_rules"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    action_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


class AutomationLog(Base):
    __tablename__ = "automation_logs"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("automation_rules.id", ondelete="CASCADE"),
        nullable=False,
    )
    trigger_event: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    execution_ms: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    old_values: Mapped[dict | None] = mapped_column(JSONB)
    new_values: Mapped[dict | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


class Interaction(Base):
    """Історія комунікацій: дзвінки/листи/SMS/зустрічі/нотатки + auto-записи автоматизацій."""

    __tablename__ = "interactions"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    deal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id", ondelete="SET NULL")
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)  # call/sms/email/meeting/note/auto
    body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


Index("ix_users_tenant", User.tenant_id)
Index("ix_clients_tenant", Client.tenant_id)
Index("ix_deals_tenant_stage", Deal.tenant_id, Deal.stage)
Index("ix_interactions_client", Interaction.client_id, Interaction.created_at.desc())


class BillingOrder(Base):
    """Рахунок за тариф: план змінюється ТІЛЬКИ після paid-вебхука (діра закрита)."""

    __tablename__ = "billing_orders"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    plan: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # liqpay/monobank
    order_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    amount_uah: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    seats_billed: Mapped[int] = mapped_column(default=1)  # amount_uah = price_per_seat * seats_billed
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/paid/failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FeedSource(Base):
    """Джерело товарів: URL фіда + розклад + маппинг. Ключі — шифровано (як integrations)."""

    __tablename__ = "feed_sources"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[dict] = mapped_column(JSONB, default=dict)  # ENCRYPTED: {type: basic/token, ...}
    format: Mapped[str] = mapped_column(String(20), default="auto")  # auto/yml/google/facebook/custom
    interval_minutes: Mapped[int] = mapped_column(default=60)  # 15/60/1440
    priority: Mapped[int] = mapped_column(default=0)  # вище = важливіше при склейці
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)  # markup_pct, rounding, exclude_*, field_map
    last_etag: Mapped[str | None] = mapped_column(Text)
    last_modified: Mapped[str | None] = mapped_column(Text)
    last_hash: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(20))  # ok/error/skipped (дубль last_status для ТЗ)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(20))  # ok/error/skipped
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


class FeedMapping(Base):
    """Візуальний маппинг «тег XML → поле CRM» + шаблони для площадок."""

    __tablename__ = "feed_mappings"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feed_sources.id", ondelete="CASCADE")
    )  # NULL = шаблон для формату (template_for)
    template_for: Mapped[str | None] = mapped_column(String(20))  # yml/google/facebook
    xml_path: Mapped[str] = mapped_column(Text, nullable=False)
    crm_field: Mapped[str] = mapped_column(String(64), nullable=False)
    transform: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


class MergeRule(Base):
    """Правило склейки на поле: source_priority / min / max / latest."""

    __tablename__ = "merge_rules"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    field: Mapped[str] = mapped_column(String(64), nullable=False)  # price/stock/name/...
    strategy: Mapped[str] = mapped_column(String(20), default="source_priority")
    source_order: Mapped[list] = mapped_column(JSONB, default=list)  # [source_id...] за пріоритетом


class FeedRun(Base):
    """Журнал запусків: скільки додано/оновлено/видалено + помилки."""

    __tablename__ = "feed_runs"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feed_sources.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="ok")  # ok/error/skipped
    added: Mapped[int] = mapped_column(default=0)
    updated: Mapped[int] = mapped_column(default=0)
    removed: Mapped[int] = mapped_column(default=0)
    errors: Mapped[dict] = mapped_column(JSONB, default=dict)
    error_text: Mapped[str | None] = mapped_column(Text)  # коротко для списку (ТЗ)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Product(Base):
    """Обʼєднаний товар (один рядок на ключ склейки після merge_rules)."""

    __tablename__ = "products"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    sku: Mapped[str] = mapped_column(Text, nullable=False)  # ключ склейки: SKU/vendorCode/GTIN
    gtin: Mapped[str | None] = mapped_column(Text)
    vendor_code: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    currency: Mapped[str] = mapped_column(String(8), default="UAH")
    stock: Mapped[int] = mapped_column(default=0)
    brand: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    images: Mapped[dict] = mapped_column(JSONB, default=list)
    attrs: Mapped[dict] = mapped_column(JSONB, default=dict)  # характеристики
    sources: Mapped[dict] = mapped_column(JSONB, default=dict)  # {source_id: offer_id}
    merged_from: Mapped[dict] = mapped_column(JSONB, default=dict)  # {поле: source_id}
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


class ProductOffer(Base):
    """Пропозиція конкретного джерела (сировина до склейки)."""

    __tablename__ = "product_offers"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL")
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feed_sources.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    currency: Mapped[str] = mapped_column(String(8), default="UAH")
    stock: Mapped[int] = mapped_column(default=0)
    raw: Mapped[dict] = mapped_column(JSONB, default=dict)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())
