-- ============================================================
-- AI Leleka CRM — MVP схема PostgreSQL (SaaS, multi-tenancy)
-- Backend: Python FastAPI + SQLAlchemy + Alembic
-- Принцип: КАЖДАЯ бизнес-таблица имеет tenant_id.
-- Все запросы бэкенда: WHERE tenant_id = :current_tenant
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------- helpers ----------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 1. TENANTS — компании-клиенты SaaS (критично для продаж)
-- ============================================================
CREATE TABLE tenants (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name          TEXT NOT NULL,                       -- "ФОП Шевченко / Магазин Лелека"
  slug          TEXT NOT NULL UNIQUE,                -- "leleka-shop" для subdomain
  plan          TEXT NOT NULL DEFAULT 'free'
                CHECK (plan IN ('free','pro','team')),
  status        TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active','suspended','deleted')),
  timezone      TEXT NOT NULL DEFAULT 'Europe/Kyiv',
  language      TEXT NOT NULL DEFAULT 'uk',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TRIGGER trg_tenants_updated
  BEFORE UPDATE ON tenants FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- 2. USERS — сотрудники внутри tenant
-- ============================================================
CREATE TABLE users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  email         TEXT NOT NULL,
  password_hash TEXT NOT NULL,                       -- bcrypt / argon2, только хеш!
  full_name     TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'manager'
                CHECK (role IN ('owner','admin','manager','viewer')),
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  last_login_at TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, email)                           -- один email может быть в разных tenants
);
CREATE INDEX idx_users_tenant ON users(tenant_id);
CREATE TRIGGER trg_users_updated
  BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- 3. CLIENTS — картки клієнтів (досьє)
-- ============================================================
CREATE TABLE clients (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  assigned_to   UUID REFERENCES users(id) ON DELETE SET NULL,
  name          TEXT NOT NULL,
  phone         TEXT,
  email         TEXT,
  source        TEXT NOT NULL DEFAULT 'manual'
                CHECK (source IN ('manual','form','prom','rozetka','import','other')),
  segment       TEXT NOT NULL DEFAULT 'new'
                CHECK (segment IN ('new','regular','vip','lost')),
  notes         TEXT NOT NULL DEFAULT '',
  gdpr_consent  BOOLEAN NOT NULL DEFAULT FALSE,      -- согласие на обработку ПД
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at    TIMESTAMPTZ                           -- soft-delete, не DELETE навсегда
);
CREATE INDEX idx_clients_tenant ON clients(tenant_id);
CREATE INDEX idx_clients_tenant_phone ON clients(tenant_id, phone);
CREATE INDEX idx_clients_assigned ON clients(assigned_to) WHERE deleted_at IS NULL;
CREATE TRIGGER trg_clients_updated
  BEFORE UPDATE ON clients FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- 4. DEALS — воронка продажів (pipeline)
-- ============================================================
CREATE TABLE deals (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  client_id     UUID NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
  manager_id    UUID REFERENCES users(id) ON DELETE SET NULL,
  title         TEXT NOT NULL,
  amount        NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (amount >= 0),
  currency      TEXT NOT NULL DEFAULT 'UAH',
  stage         TEXT NOT NULL DEFAULT 'new'
                CHECK (stage IN ('new','contacted','negotiation','won','lost')),
  loss_reason   TEXT,                                -- для AI-анализа причин потерь
  probability   INT NOT NULL DEFAULT 0 CHECK (probability BETWEEN 0 AND 100),
  expected_close_date DATE,
  last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), -- для триггера "зависла 3 дни"
  won_at        TIMESTAMPTZ,
  lost_at       TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_deals_tenant ON deals(tenant_id);
CREATE INDEX idx_deals_tenant_stage ON deals(tenant_id, stage);
CREATE INDEX idx_deals_client ON deals(client_id);
CREATE INDEX idx_deals_stuck ON deals(tenant_id, last_activity_at)
  WHERE stage NOT IN ('won','lost');                  -- быстрый поиск "зависших"
CREATE TRIGGER trg_deals_updated
  BEFORE UPDATE ON deals FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- 5. TASKS — задачі й нагадування ("будильник менеджера")
-- ============================================================
CREATE TABLE tasks (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  deal_id       UUID REFERENCES deals(id) ON DELETE CASCADE,
  client_id     UUID REFERENCES clients(id) ON DELETE CASCADE,
  assignee_id   UUID REFERENCES users(id) ON DELETE SET NULL,
  title         TEXT NOT NULL,
  description   TEXT NOT NULL DEFAULT '',
  due_at        TIMESTAMPTZ,
  status        TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open','done','cancelled')),
  priority      TEXT NOT NULL DEFAULT 'normal'
                CHECK (priority IN ('low','normal','high')),
  completed_at  TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_tasks_tenant_assignee ON tasks(tenant_id, assignee_id) WHERE status = 'open';
CREATE INDEX idx_tasks_due ON tasks(due_at) WHERE status = 'open';
CREATE TRIGGER trg_tasks_updated
  BEFORE UPDATE ON tasks FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- 6. INTEGRATIONS — API-ключи Prom/Rozetka/NP/Checkbox/LiqPay
-- Хранить credentials ТОЛЬКО зашифрованными ( Fernet / KMS ),
-- в коде — адаптер на каждого провайдера, не прямые вызовы.
-- ============================================================
CREATE TABLE integrations (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  provider      TEXT NOT NULL
                CHECK (provider IN ('prom','rozetka','novaposhta','checkbox','liqpay','monobank')),
  credentials   JSONB NOT NULL DEFAULT '{}',          -- ENCRYPTED! {"api_key": "enc:..."}
  settings      JSONB NOT NULL DEFAULT '{}',          -- {"warehouse_from": "Київ-1", ...}
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  last_sync_at  TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, provider)                        -- 1 подключение на провайдера
);
CREATE INDEX idx_integrations_tenant ON integrations(tenant_id);
CREATE TRIGGER trg_integrations_updated
  BEFORE UPDATE ON integrations FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- 7. WEBHOOK_EVENTS — inbox вебхуков с ретраями (retry)
-- Адаптеры: Prom/Rozetka/NP шлют сюда -> воркер разбирает.
-- Без этого при сбое сети заказы теряются молча.
-- ============================================================
CREATE TABLE webhook_events (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID REFERENCES tenants(id) ON DELETE CASCADE,
  -- tenant_id nullable: если не смогли распознать tenant по токену — все равно сохраняем для разбора
  provider      TEXT NOT NULL,
  external_id   TEXT,                                -- id заказа у маркетплейса (идемпотентность)
  payload       JSONB NOT NULL DEFAULT '{}',          -- сырое тело вебхука
  status        TEXT NOT NULL DEFAULT 'received'
                CHECK (status IN ('received','processing','processed','failed')),
  retry_count   INT NOT NULL DEFAULT 0,
  next_retry_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  error         TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (provider, external_id)                      -- защита от дублей
);
CREATE INDEX idx_webhook_retry ON webhook_events(status, next_retry_at)
  WHERE status IN ('received','failed');
CREATE INDEX idx_webhook_tenant ON webhook_events(tenant_id);
CREATE TRIGGER trg_webhook_updated
  BEFORE UPDATE ON webhook_events FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- 8. AUTOMATION_RULES — правила "якщо -> то" (конструктор)
-- ============================================================
CREATE TABLE automation_rules (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name          TEXT NOT NULL,                       -- "Новый лид -> назначить менеджера"
  trigger_type  TEXT NOT NULL
                CHECK (trigger_type IN ('new_lead','deal_stuck','payment_received','no_response','deal_won','deal_lost')),
  trigger_config JSONB NOT NULL DEFAULT '{}',        -- {"stuck_days": 3, "stages": ["contacted"]}
  action_type   TEXT NOT NULL
                CHECK (action_type IN ('assign_manager','notify','create_ttn','send_message','request_review','move_segment','create_task')),
  action_config JSONB NOT NULL DEFAULT '{}',         -- {"channel": "sms", "template": "..."}
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  priority      INT NOT NULL DEFAULT 0,
  created_by    UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_rules_tenant_trigger ON automation_rules(tenant_id, trigger_type) WHERE is_active = TRUE;
CREATE TRIGGER trg_rules_updated
  BEFORE UPDATE ON automation_rules FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- 9. AUTOMATION_LOGS — история срабатываний (без нее отладка невозможна)
-- "Сработало 15 раз, 2 с ошибкой" — отвечает эта таблица.
-- ============================================================
CREATE TABLE automation_logs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  rule_id       UUID NOT NULL REFERENCES automation_rules(id) ON DELETE CASCADE,
  trigger_event JSONB NOT NULL DEFAULT '{}',          -- что запустило: {"deal_id": "...", "event": "deal_stuck"}
  status        TEXT NOT NULL
                CHECK (status IN ('success','failed','skipped')),
  error_message TEXT,
  execution_ms  INT,                                  -- сколько выполнялось
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_autolog_rule ON automation_logs(rule_id, created_at DESC);
CREATE INDEX idx_autolog_tenant ON automation_logs(tenant_id, created_at DESC);

-- ============================================================
-- 10. AUDIT_LOG — журнал "хто що змінив" (доверие клиента)
-- Пишет бэкенд-middleware при каждом CREATE/UPDATE/DELETE/EXPORT/LOGIN.
-- old_values/new_values — для расследования "кто удалил клиента".
-- ============================================================
CREATE TABLE audit_log (
  id            BIGGENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  actor_id      UUID REFERENCES users(id) ON DELETE SET NULL,
  entity_type   TEXT NOT NULL,                       -- 'client' | 'deal' | 'task' | 'integration' | ...
  entity_id     TEXT NOT NULL,
  action        TEXT NOT NULL
                CHECK (action IN ('create','update','delete','login','export','restore')),
  old_values    JSONB,
  new_values    JSONB,
  ip            TEXT,
  user_agent    TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_tenant_entity ON audit_log(tenant_id, entity_type, entity_id, created_at DESC);
CREATE INDEX idx_audit_actor ON audit_log(actor_id, created_at DESC);

-- ============================================================
-- ЗАМЕЧАНИЕ ДЛЯ FASTAPI:
-- 1. Во всех SELECT/UPDATE/DELETE обязателен фильтр tenant_id.
--    Удобно: dependency get_current_tenant() -> tenant_id из JWT.
-- 2. credentials в integrations шифровать до INSERT (cryptography.Fernet).
-- 3. В PII-поля (phone/email) для AI-аналитики отправлять только
--    знеособлені агрегаты, не сырые значения (GDPR).
-- ============================================================
