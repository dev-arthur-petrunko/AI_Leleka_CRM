# AI Leleka CRM — MVP (FastAPI + PostgreSQL)

## Запуск
```bash
docker compose up --build
# API: http://localhost:8000/docs
# Health: http://localhost:8000/health
```

Без Docker:
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Что уже есть
- `db/schema.sql` — SaaS-схема: tenants, users, clients, deals, tasks, integrations, webhook_events, automation_rules/logs, audit_log
- `backend/app/models/` — SQLAlchemy-модели 1-в-1
- `backend/app/core/deps.py` — `get_current_tenant()` из JWT, `require_role()`
- Routers: `/auth`, `/clients`, `/deals`, `/tasks`, `/webhooks`
- Webhook inbox с дедупликацией `(provider, external_id)` и ретраями

## Правила
1. Каждый запрос к бизнес-таблицам: `WHERE tenant_id = current_tenant`
2. `credentials` в integrations — только шифрованные (Fernet)
3. В AI API — только знеособлені дані (GDPR)
