# AI Leleka CRM — SaaS для малого бізнесу України (FastAPI + PostgreSQL)

План робіт агента: `docs/AGENT_PLAN.md` (фази 0–8). Памʼять: `CLAUDE.md`, навички `.claude/skills/`.

## Запуск (dev)
```bash
cp backend/.env.example backend/.env
# в .env вписати SECRET_KEY (openssl rand -hex 32) і CREDENTIALS_KEY (Fernet generate_key)
docker compose up --build
# API: http://localhost:8000/docs
```
Без Docker — ті ж змінні в env, далі `uvicorn app.main:app --reload` з `backend/`.
Тести: `TEST_DATABASE_URL=... alembic upgrade head && pytest -q` з `backend/`.

## Прод
`docker-compose.prod.yml` (БД/Redis без зовнішніх портів, gunicorn/2 воркери, worker+beat, місце під Caddy).
Бекап: `scripts/backup.sh` (cron 03:00). Моніторинг: `SENTRY_DSN` опційно.

## Безпека (критично)
- Старі дефолтні секрети з репозиторію **скомпрометовані** (репо публічне): без `SECRET_KEY`≥32 app не стартує.
- **Ротація на проді:** згенеруй новий `SECRET_KEY`, поклади в env сервера, перезапусти — усі старі токени миттєво стануть невалідними (це добре). Старе значення з історії git вважати зламаним назавжди.
- Ключі інтеграцій у БД — тільки Fernet-шифровані (`encrypt_credentials` у upsert, GET їх не повертає).
- RBAC: write — owner/admin/manager; інтеграції — owner/admin; upgrade тарифу — тільки owner (+audit).
- Платні фічі (`ai_analytics`, `marketplace`, `novaposhta`, `fiscal`) гейтяться на API (402), не лише в UI.
- Апгрейд тарифу: тільки owner; платний — рахунок (`billing_orders` pending) + інвойс LiqPay/Mono, план змінюється лише paid-вебхуком з перевіркою підпису. Без PLATFORM-ключів — 409.
- Rate-limit: 10/хв на `/auth/login`. CORS — лише `FRONTEND_ORIGINS`.
- Міграції: `backend/alembic/` підключено (`alembic revision --autogenerate`, `upgrade head`).

## Що вже є
- SaaS-схема (30+ таблиць): tenants/users, clients/deals/tasks, integrations/webhook_events (підписані),
  automation_*, analytics, billing_orders, feed_* + products, orders/order_items/payments/shipments/returns,
  tags/custom/pipelines, conversations/messages/templates, sync_state/lead_forms
- Routers: `/auth` (invite, 2FA, refresh, reset, telegram), `/clients` (+erase), `/deals`, `/tasks`,
  `/webhooks` (підписані), `/automations`, `/analytics` + `/analytics/shop` (виручка, AOV, LTV, RFM, повернення, прогноз),
  `/billing` (per-seat + вебхуки оплати), `/integrations`, `/feedhub`, `/orders`, `/inbox`, `/forms`, `/notifications`
- Celery-воркер + beat (вебхуки, sync, НП-трекінг, stuck, білінг, фіди); cron-скрипти лишились CLI-обгортками
- Превʼю `frontend-preview/` (таб-бар: Дашборд, Замовлення, Вхідні, Клієнти, Ще; чесний api.js без мовчазних моків)
- React `frontend/` (glass, TanStack Query, Ctrl+K) + `bot/` (aiogram, потрібен BOT_TOKEN)

## Правила
1. Каждый запрос к бизнес-таблицам: `WHERE tenant_id = current_tenant`
2. `credentials` в integrations — только шифрованные (Fernet)
3. В AI API — только знеособлені дані (GDPR)
