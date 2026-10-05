"""SQLAlchemy-модели 1-в-1 под db/schema.sql."""

import uuid
from datetime import UTC, datetime

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


def _utcnow():
    return datetime.now(UTC)


def _now():
    # default=_now() обчислюється при імпорті — повертаємо callable,
    # щоб кожен рядок отримував СВІЙ час (і з таймзоною, не naive).
    return _utcnow


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
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    email_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_id: Mapped[str | None] = mapped_column(Text)  # привʼязка для Mini App входу
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)  # UI: theme_mode, timezone...
    token_version: Mapped[int] = mapped_column(default=0)  # відкликання токенів
    totp_secret: Mapped[str | None] = mapped_column(Text)  # 2FA (зашифровано)
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
    temperature: Mapped[str | None] = mapped_column(
        String(10))  # hot/warm/cold вручну; null = авто-скоринг
    notes: Mapped[str] = mapped_column(Text, default="")
    custom: Mapped[dict] = mapped_column(JSONB, default=dict)  # кастомні поля (фаза 2.5)
    consents: Mapped[dict] = mapped_column(JSONB, default=dict)  # {channel: {granted_at, source}}
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
    converted_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL")
    )  # угода → замовлення (ідемпотентна конвертація, UI-5)
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
    webhook_secret: Mapped[str | None] = mapped_column(Text)  # секрет вебхука (шифровано)
    status: Mapped[str] = mapped_column(String(20), default="ok")  # ok/error/auth_failed/paused
    last_error: Mapped[str | None] = mapped_column(Text)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("tenant_id", "provider", "external_id"),)
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
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


class SyncState(Base):
    """Курсор polling-синхронізації на інтеграцію (фаза 3.3)."""

    __tablename__ = "sync_state"
    __table_args__ = (UniqueConstraint("tenant_id", "integration_id"),)
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("integrations.id", ondelete="CASCADE"), nullable=False
    )
    cursor: Mapped[str | None] = mapped_column(Text)  # дата/offset, залежить від провайдера
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(default=0)


class LeadForm(Base):
    """Публічна форма прийому заявок з сайту (honeypot + секрет)."""

    __tablename__ = "lead_forms"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    secret: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


class PasswordResetToken(Base):
    """Одноразовий токен скидання пароля: зберігаємо ТІЛЬКИ хеш, живе 30 хв."""


    __tablename__ = "password_reset_tokens"
    id: Mapped[uuid.UUID] = _uuid()
    email: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


# ================= Фаза 2: модель магазину =================

class Order(Base):
    """Замовлення магазину. Ідемпотентність: UNIQUE(tenant_id, source, external_id)."""

    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("tenant_id", "source", "external_id"),)
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL")
    )
    deal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id", ondelete="SET NULL")
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # prom/rozetka/site/manual
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    order_number: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="new")
    payment_status: Mapped[str] = mapped_column(String(20), default="unpaid")
    payment_method: Mapped[str | None] = mapped_column(String(20))
    currency: Mapped[str] = mapped_column(String(8), default="UAH")
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    discount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    shipping_cost: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    placed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw: Mapped[dict] = mapped_column(JSONB, default=dict)
    custom: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL")
    )
    sku: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    qty: Mapped[float] = mapped_column(Numeric(12, 3), default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    discount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("tenant_id", "provider", "external_id"),)
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Shipment(Base):
    __tablename__ = "shipments"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    carrier: Mapped[str] = mapped_column(String(20), default="novaposhta")
    ttn: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(64))
    status_code: Mapped[str | None] = mapped_column(String(32))
    cod_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Return(Base):
    __tablename__ = "returns"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    status: Mapped[str] = mapped_column(String(20), default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())
    source: Mapped[str] = mapped_column(String(20), default="manager")  # provider/manager/auto


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    color: Mapped[str | None] = mapped_column(String(16))


class EntityTag(Base):
    """Привʼязка тега до сутності (client/order/deal)."""

    __tablename__ = "entity_tags"
    __table_args__ = (UniqueConstraint("tenant_id", "tag_id", "entity_type", "entity_id"),)
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)


class CustomFieldDef(Base):
    """Визначення кастомного поля; значення — у JSONB custom сутностей."""

    __tablename__ = "custom_fields"
    __table_args__ = (UniqueConstraint("tenant_id", "entity", "key"),)
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    entity: Mapped[str] = mapped_column(String(20), nullable=False)  # client/order
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    ftype: Mapped[str] = mapped_column(String(20), default="text")  # text/number/date/bool


class Pipeline(Base):
    __tablename__ = "pipelines"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class PipelineStage(Base):
    __tablename__ = "pipeline_stages"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(default=0)


Index("ix_orders_tenant_status", Order.tenant_id, Order.status)
Index("ix_orders_tenant_placed", Order.tenant_id, Order.placed_at)
Index("ix_orders_tenant_client", Order.tenant_id, Order.client_id)


class SavedView(Base):
    """Збережені види списків (UI-5): фільтри користувача на сутність."""

    __tablename__ = "saved_views"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", "entity", "name"),)
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    entity: Mapped[str] = mapped_column(String(20), nullable=False)  # deals/orders/clients
    name: Mapped[str] = mapped_column(Text, nullable=False)
    filters: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


class Conversation(Base):
    """Діалог з клієнтом в одному каналі (фаза 5.1)."""

    __tablename__ = "conversations"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL")
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # in/out
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="delivered")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now())


class MessageTemplate(Base):
    """Шаблони з підстановками {{client.first_name}} {{order.number}} {{shipment.ttn}}."""

    __tablename__ = "message_templates"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)
    id: Mapped[uuid.UUID] = _uuid()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)


Index("ix_conv_tenant_client", Conversation.tenant_id, Conversation.client_id)
Index("ix_msg_conv", Message.conversation_id, Message.created_at)
