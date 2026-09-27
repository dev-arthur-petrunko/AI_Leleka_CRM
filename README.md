# AI Leleka CRM — MVP (FastAPI + PostgreSQL)

## Запуск
```bash
cp backend/.env.example backend/.env
# в .env вписати SECRET_KEY (openssl rand -hex 32) і CREDENTIALS_KEY (Fernet generate_key)
docker compose up --build
# API: http://localhost:8000/docs
```
Без Docker — ті ж змінні в env, далі `uvicorn app.main:app --reload` з `backend/`.

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
- SaaS-схема (11 таблиць: +`interactions` — таймлайн комунікацій)
- Routers: `/auth` (+invite), `/clients` (+пошук/фільтри/пагінація, CSV-імпорт, interactions), `/deals` (+фільтри, CSV-експорт), `/tasks`, `/webhooks`, `/automations`, `/analytics` (платно), `/billing`, `/integrations` (шифр + SMS), `/notifications` (Redis-інбокс)
- Движок автоматизацій викликає **реальні** адаптери: ТТН НП, SMS SendPulse/TurboSMS; кожна дія пише слід у interactions
- Превʼю фронту `frontend-preview/` (8 екранів + login, Telegram-стиль, toast, скелетони, empty states; dashboard тягне живі дані при наявності токена, інакше мок)
- Щомісячний перерахунок місць: `python -m app.workers.billing_recalc` (cron 1-го числа; авто-рахунки — наступний крок)

## Правила
1. Каждый запрос к бизнес-таблицам: `WHERE tenant_id = current_tenant`
2. `credentials` в integrations — только шифрованные (Fernet)
3. В AI API — только знеособлені дані (GDPR)
