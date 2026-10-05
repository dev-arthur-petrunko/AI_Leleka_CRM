# AI Leleka CRM — полный разбор проекта

> Написано по факту кода, октябрь 2026. Коммитов: 68, ветка `main`.
> Бэкенд: 19 API-модулей, 36 таблиц, 12 миграций, 96 тестов (92 passed + 4 skip: лендинг+Caddy skip без фронта/Caddyfile в контейнері).
> Фронт: 15 экранов, 73 ключа `uk.json`, сборка ~7 с (main 381КБ + lazy Analytics).
> Если строка ниже противоречит коду — верь коду и поправь строку.

---

## 1. Паспорт

SaaS-CRM для украинского интернет-магазина: заказы с Prom/Rozetka/сайта,
Нова Пошта, касса и оплата (LiqPay/Mono), Telegram и AI — в одном месте.
Позиционирование: настройка за 15 минут, гривна, Telegram-first, украинский язык.

| Слой | Факт |
|---|---|
| API | FastAPI 0.115, SQLAlchemy 2.0, Pydantic 2.9/Settings 2.5, Alembic 1.13, slowapi (rate-limit) |
| БД / очередь | PostgreSQL 16, Redis 7, Celery 5.4 (worker + beat) |
| Фронт | Vite 5 + React 18 + TS 5, TanStack Query 5, React Router 6, Recharts, lucide-react |
| Бот | aiogram 3.15 + apscheduler |
| Инфра | Docker Compose (dev + prod), Caddy 2 (прод), GitHub Actions (3 jobs), Playwright-снапшоты |

---

## 2. Быстрый старт (проверено живьём)

### Dev

```bash
cp backend/.env.example backend/.env
# в .env: SECRET_KEY (openssl rand -hex 32), CREDENTIALS_KEY (Fernet generate_key)
docker compose up --build -d
# API: http://localhost:8000/docs, фронт: cd frontend && npm i && npm run dev
```

Сервисы: `db` (5432 наружу), `redis` (6379 наружу), `api`
(`alembic upgrade head && uvicorn --reload`, 8000), `worker` (concurrency 2), `beat`.
`SECRET_KEY` короче 32 — app падает на импорте (так задумано, старые дефолты
из истории git считаются скомпрометированными).

### Тесты бэкенда

```bash
docker compose exec -T -e DATABASE_URL=postgresql+psycopg2://leleka:leleka@db:5432/leleka_test \
  api alembic upgrade head
docker compose exec -T -e DATABASE_URL=postgresql+psycopg2://leleka:leleka@db:5432/leleka_test \
  api python -m pytest -q
# → 92 passed, 4 skipped
```

Три нюанса, в которых легко ошибиться:
1. `conftest.py` **отказывается стартовать**, если БД не `*_test`, и приравнивает
   `DATABASE_URL` к тестовой — воркер (`SessionLocal`) физически не может
   задеть dev-базу. Без этого один тест молча писал бы в рабочую БД.
2. После смены `backend/requirements.txt` — `docker compose build api worker beat`,
   иначе в образе старые зависимости (было: не хватало pytest/httpx/celery).
3. Тестовая БД копит мусор между прогонами (perf-тест создаёт 10k сделок);
   при странных тормозах — truncate бизнес-таблиц в `leleka_test`.

### Фронт

```bash
cd frontend && npm i && npx tsc --noEmit && npm run build
node scripts/check-contrast.mjs   # 16/16 пар, 0 fail
python scripts/snapshots.py --serve 5174 --api http://localhost:8000
# 24 кадра (6 экранов × 390/1280 × Ранок/Вечір), проверка overflow и JS-ошибок
```

Снапшоты требуют dist, собранный с `VITE_API_BASE=http://localhost:8000`,
после прогона — пересобрать чистый (`npm run build` без переменной).
Кадры лежат в `frontend/snapshots/` (в `.gitignore`, в репо не коммитятся).

### Прод

`docker-compose.prod.yml` + `Caddyfile`: БД/Redis без внешних портов,
`uvicorn --workers 2 --proxy-headers --forwarded-allow-ips='*'`
(за Caddy все IP выглядели бы одним — счётчики slowapi общие через Redis,
при его падении fallback в память), healthcheck у api и db, фронт собирается
сервисом `frontend` (`npm ci && build` → том `frontend_dist`).
Caddy делит трафик **по `Accept`**: навігація (`text/html`) → SPA,
fetch (`*/*`) → API по списку префиксов (покриття перевіряє
`test_caddy_routes`); `/docs`+`/openapi.json`+`/redoc` в прод не проксуються;
`?secret=` redactиться в логах + `log_skip /webhooks*`; остальное — 404.
Переменные: `DB_*`, `REDIS_PASSWORD`, `SECRET_KEY`,
`CREDENTIALS_KEY`, `DOMAIN`, `FRONTEND_ORIGINS=https://DOMAIN`,
`PLATFORM_LIQPAY_*`, `PLATFORM_MONO_TOKEN`, `ANTHROPIC_API_KEY`,
`BOT_TOKEN` (= `TELEGRAM_BOT_TOKEN` для API), `SENTRY_DSN`.
Бот — отдельным профилем: `docker compose --profile bot up -d`
(без токена `up -d` не должен падать).
Сброс пароля ходит через **активную `email`-интеграцию** в БД, env-переменных
SMTP нет — заведите интеграцию, иначе токен только в логе. Бекап: `scripts/backup.sh`.

---

## 3. Сквозные механизмы

**Мультитенантность.** `tenant_id` — только из JWT (`get_current_tenant`),
никогда из body/query. Каждый запрос к бизнес-таблицам фильтрует по нему;
уникальности вида `UNIQUE(tenant_id, ...)`. Тест изоляции покрывает заказы,
вхідні, інтеграції, повідомлення, пошук, види, тариф, audit (файл
`test_tenant_isolation.py` + точечные тесты).

**Аутентификация.** Access (60 хв) + refresh (7 днів), `token_version` отзывает
всё при смене пароля. Login: `username=email`, `client_id=slug компанії`
(при дублях email без slug — 400 с требованием компании), `scope=код 2FA`.
401 → клиент пробует refresh один раз → иначе logout. Регистрация создаёт
тенант+owner и шлёт HMAC-токен подтверждения почты (24 ч, без миграции;
вход НЕ блокируется — мягкое). Приглашённый входит по временному паролю
и принудительно идёт на `/password` (`must_change_password` гейтит всё,
кроме смены пароля/`/me`/refresh — и на бэке, и редиректом во фронте).
2FA TOTP для owner/admin (`/2fa/setup` → QR, `/2fa/enable` → код).

**RBAC.** write — owner/admin/manager; интеграции/тариф-апгрейд — owner
(интеграции list/test — owner/admin). Менеджер видит 403 с людским текстом.

**Paywall.** `require_plan_feature`: весь `/analytics` требует `ai_analytics`
(402), провайдеры — через `_gate` (402). Базовые `/analytics/shop/*` —
бесплатно (решение). Без PLATFORM-ключей платный апгрейд — 409.

**Прочее.** Rate-limit: login 5–10/мин, confirm/register/refresh — тоже;
тело вебхука ≤1 МБ; CORS только из `FRONTEND_ORIGINS`; `X-Request-ID` на каждый
ответ; телефоны — только через `normalize_phone` (`050…`/`380…` → `+380…`,
мусор → `None`); ключи интеграций — только Fernet-шифрованные, GET их
не отдаёт (только `has_key`); бесплатный Team закрыт (счёт × места).

**Вебхуки.** Единственный приём — `POST /webhooks/{provider}/{integration_id}`:
секрет (`X-Webhook-Secret`/`?secret=`, `compare_digest`) или HMAC тела
(`X-Signature`); unknown/inactive/без секрета — 404/401 без подробностей.
Legacy `?tenant=slug` **удалён** (принимал без секрета). Дедуп
`UNIQUE(tenant_id, provider, external_id)`; пустой external_id → `sha256` тела.
`GET /pending` — только owner/admin своего тенанта.

**Синхронизация (polling — основной путь, вебхуки — ускоритель).**
`sync_state` на интеграцию: тянем от курсора (ISO-дата **последнего
обработанного** заказа, не «сейчас»), пачками до 100, до 10 итераций;
стоп — короткая страница или ноль новых. Курсор движется только вперёд
и только после успеха. Без номера — стабильный `sync-<sha16 от тела>`
(**без позиции в пачке**, иначе переупорядочивание = дубли).
Даты нормализуются к ISO (ISO/`дд.мм.рррр`/unix; что не распознано — сырьём). Позиции передаются в `upsert_order`.
Провал (включая 429 с уважением к `Retry-After`) — курсор стоит, пишется
ошибка; 401/403 → `auth_failed`. Без ключа — честный `not_connected`,
а не `ok`. Prom шлёт `date_from`; Rozetka его не задокументировала —
принимаем, но не отправляем (останавливаемся по seen-набору).

**Upsert заказа.** Единая точка (`services/orders.py::upsert_order`):
клиент по телефону→email, `INSERT … ON CONFLICT (tenant_id, source,
external_id)` (повтор = тот же заказ), позиции пересинхронизируются,
смена статуса → `order_status_history` + автоматизации, новому заказу —
черновая угода для канбана. Импорт CSV — через тот же upsert (до 2000 строк,
5 МБ).

**Автоматизации.** Движок «если → то»: триггеры (`new_lead`, `deal_stuck`,
`payment_received`, `order_*`, …) + условия (стадии, суммы) → действия
(менеджер, ТТН, письмо, задача, отзыв…). Каждый прогон — в `automation_logs`
со статусом. Кнопка «5 правил одним кліком» идемпотентна (по именам).

**Уведомления.** `notify.push/pull` — Redis-список `notif:{tenant}` (100 шт):
ошибки фидов, stale-алерты. UI тянет опросом 30 с; эмодзи из серверных
текстов на фронте чистятся.

**AI-скоринг (честный).** `score_deal`: стадия + свежесть + сумма + сегмент →
0–100 → hot/warm/cold. **Ручная температура клиента сильнее скоринга**
(hot тянет ≥70, cold жмёт ≤39). Во внешний AI — только агрегаты без PII
(`anonymize_deals`, `pii_sent=False`).

---

## 4. Бэкенд по роутерам

| Роутер | Префикс | Методы и логика |
|---|---|---|
| `auth` | `/auth` | register (тенант+owner+письмо-подтверждение), login, refresh, change-password (отзывает токены), reset-request/confirm (30 хв, только хеш), 2fa/setup+enable, invite (временный пароль+must_change), telegram/link (проверка initData), `GET /me` (роль, преференсы, must_change, email_confirmed), `PATCH /me/preferences` (тема, сайдбар, анимации — синк между устройствами), confirm-email |
| `audit` | `/audit` | чтение `audit_log` своего тенанта (лимит 100) с email актора |
| `clients` | `/clients` | список (пошук з варіантами регістру кирилиці, `segment`, пагинация), создание, `PATCH /{id}` (имя/телефон с нормализацией/email/**segment/temperature** + audit), import-csv (фиксированные колонки, 1000, 5 МБ), interactions list/add, soft-`DELETE`, `/erase` (обезличивание, owner/admin) |
| `messages` | `/clients` | `/{id}/message-preview` (AI-текст до отправки + `can_send`/`send_hint`), `/{id}/message` (422 без контакта канала; пишет в interactions) — коллизии с `clients.py` нет (подпути разные) |
| `deals` | `/deals` | список (`stage`, `manager_id`), создание, `PATCH /{id}` (назва/сума/клієнт/менеджер/ймовірність, чужі — 400/404), `/export`, `/stuck`, `PATCH /{id}/stage` (причина програша обязательна; вероятность = f(стадия; `won_at`/`lost_at`; триггеры), `POST /{id}/convert-to-order` (идемпотентно, создаёт заказ `confirmed`), `POST /{id}/unlink-order` (рвёт связь, **заказ живёт**) |
| `orders` | `/orders` | список (status/source/payment/date/q, пагинация), карточка (позиции/платежи/ТТН/история), создание, `PATCH /{id}/status` (**валидация + строка истории `manager`**), import-csv с маппингом, `/export`, `/{id}/shipments` (**реальный** вызов НП, ТТН/`STUB`), `/{id}/returns`, `/tags/*`, `/custom-fields` (CRUD), `/pipelines` (дефолт при пусто) |
| `tasks` | `/tasks` | список (`status`, `assignee_id`), создание, `PATCH /{id}` (статус/пріоритет — `completed_at` сам), `DELETE /{id}` |
| `webhooks` | `/webhooks` | signed-ingest, `GET /pending` (owner/admin) |
| `automations` | `/automations` | rules CRUD, `seed-defaults` (5 штук), logs, stats («сработало N, ошибок M») |
| `analytics` | `/analytics` | kpi/funnel/hot-leads/forecast/churn/loss-reasons/next-actions/dashboard одним запросом (платно) |
| `shop` | `/analytics/shop` | revenue (по днях + AOV), ltv (топ + repeat_rate), rfm (`NTILE(5)` по delivered), returns (rate/count/by_reason/lost), forecast-range (взвешенная воронка + скользящее среднее → диапазон) |
| `billing` | `/billing` | plans/current (места/сумма/фичи), upgrade (только owner; 0 → сразу, иначе счёт + LiqPay-форма/Mono-ссылка), orders (история счетов), вебхуки LiqPay/Mono с проверкой подписи (Mono сверяется сервер-сервер), `_confirm_paid` идемпотентен |
| `integrations` | `/integrations` | CRUD (ключи шифруются, секрет вебхука генерится), `/{p}/test` (реальный ping; novaposhta/checkbox/liqpay/mono/sms — тестовые вызовы), `/{p}/import-orders` (идемпотентно), `/{p}/webhook-url` (URL+секрет+инструкция) |
| `feedhub` | `/feedhub` | sources CRUD/run, runs, products, preview, mapping, merge-rules, `export.xml` |
| `inbox` | `/inbox` | conversations (фильтр статуса), тред (conversation+messages), `PATCH` (assignee/status), reply (Telegram-реально, остальные — stub+очередь), templates CRUD, telegram-inbound (сопоставление по chat_id → лид) |
| `forms` | `/api/v1/forms` + `/forms` | публичный приём заявок (секрет формы, honeypot, rate-limit) → клієнт+угода |
| `notifications` | `/notifications` | pull Redis-инбокса |
| `search` | `/search`, `/today` | поиск (клієнти ≤5/угоди ≤5/замовлення ≤5, телефоны нормализуются; `q` ≥ 2) + «Що зробити зараз» (прострочені/завислі 3д/новые+confirmed/открытые диалоги) |
| `views` | `/views` | сохранённые фильтры (свои + общие) |
| `shop`/`health` | — | `GET /health` публичный |

**Сервисы.** `orders.upsert_order` (выше); `sync` (выше); `ai` (скоринг,
прогноз скользящим средним, churn одним SQL, next-actions двумя запросами);
`messaging` (AI-текст только из названия товара + локальные подстановки
`{{client.first_name}}`/`{{order.number}}`/`{{shipment.ttn}}`);
`billing` (`PLANS`: free 1 место/0 ₴, pro 5/350, team 10/300; `check_seats`
402 при переполнении); `notify` (Redis); `feedhub` (fetch с ETag/304 и
SSRF-guard, `defusedxml` против XXE, merge-стратегии); `shipments.poll_shipments`
(трекинг НП → delivered/returned + задача); `automation/actions` (исполнители).

**Адаптеры** (`integrations/`): `BaseAdapter` (ретраи 3×, 429 с `Retry-After`
до 30 с, `stub()` без ключей). Prom (`token`; `date_from`/`limit`/`status`;
`set_status` обратно), Rozetka (`token`, протухает — refresh не automatизован,
зафиксировано), Nova Poshta (`api_key`; создание + трекинг ТТН),
Checkbox (`login/password`), LiqPay (`public/private`), Mono (`token`),
SendPulse/TurboSMS, Telegram (`bot_token`), Viber (`auth_token`), Email (SMTP),
SMS. Подсказки ключей зашиты в мастере подключений во фронте.

**Модели/миграции.** 36 таблиц: tenants/users, clients/deals/tasks,
orders/items/payments/shipments/returns/history, integrations/webhook_events,
automations+logs, conversations/messages/templates, feed_*/products,
billing_orders, tags/custom/pipelines, sync_state/lead_forms, audit_log,
saved_views, notifications нет (Redis). 12 миграций, HEAD
`e2f3a4b5c6d7_client_temperature`; у всех есть downgrade; `db/schema.sql`
— эталонная копия схемы (обновлять руками вслед за миграциями).

**Воркеры/beat.** `process_webhook_batch` каждые 30 с (SKIP LOCKED, backoff
`min(2^n,60м)`, dead после 10); `sync_due_integrations` каждые 10 мин;
`run_stuck_check` ежечасно (лимит 200, иначе виснет на больших базах);
`run_feed_scheduler` каждые 15 мин (+stale-алерты 6 ч); `run_np_poll`
каждые 45 мин; `billing_recalc` 1-го числа 09:00 (только отчёт о дельте мест).
Schedule-файл beat — в `/tmp` (битый файл в volume ронял сервис).
`check_stuck`/`recalc`/`run_due` покрыты тестами.

**Бот** (`bot/`, aiogram 3): `/start` с deep-link, кнопки-заглушки
(дёрнуть CRM API — TODO), дайджесты 09:00/18:00 — пока лог-заглушка
(подписок по тенантам нет в модели — честно). В compose — профиль `bot`.

---

## 5. Фронтенд

**Каркас** (`App.tsx`). ≥1024px — сворачиваемая рейка (Ctrl+B, бейджи:
задачи/вхідні/замовлення/інтеграції/сповіщення); <1024px — нижнее меню
из 5 иконок; шапка: крошки, поиск Ctrl+K (палитра: клієнти/угоди/замовлення
+ действия), «+ Створити», колокольчик с пульс-бейджем, тема.
Контейнер ≤1440px, `main` с `key=pathname` (переход 150мс), catch-all → `/`,
принудительный `/password` при `must_change_password`.

**API-клиент** (`api.ts`). `HttpError(status)` на любой не-OK (402/403
видны экранам, а не молчат); 401 → один refresh → иначе logout+`/login`;
таймаут 8 с; `login(email, password, company?, totp?)`,
`register(...)`, `API_BASE` наружу. Контракта `{ok,…}` нет — не нужен:
`useQuery.error` реально сетится.

**i18n** (`uk.json`, 73 ключа): `nav.*` (13+), `action.*`, `state.*`,
`stage.*`, `score.*` (hot/warm/cold), `segment.*`, `source.*`, `order.*` (7),
`pay.*` (4), `prio.*`, `feed.*`, `ch.*`/`conv.*`, `theme.*`, `temp.*`.
Сырые коды в UI запрещены (проверено grep-аудитом).

**Экраны** (все — Skeleton/Empty с действием/Error с повтором):

| Экран | Данные и действия |
|---|---|
| Головна `/` | Привітання за часом + онбординг «Старт за 5 хвилин» (магазин/замовлення/правила/команда + прогрес) + групи «Прострочені / Нові / Без руху / Непрочитані» |
| Угоди `/deals` | Канбан на **Pointer Events** (миша+тач, ghost їде за курсором через rAF, плейсхолдер, автоскролл, отмена 8 с) + таблиця з селектом стадії; «Мої» через `manager_id`; створення; види (створити/застосувати); **клік по картці — редактор** (назва/сума/клієнт); дрібний підпис клієнта; **температура клієнта на картці** (селект, скоринг перераховується); конвертація → замовлення (fullscreen-свято), причина програшу; меню звʼязку «Відкрити/Розірвати» (замовлення живе) |
| Замовлення `/orders` | Картки (№+джерело, чипи статусу/оплати, сума) + **drawer**: позиції, оплати, лінія кроків зі «їдучою» машинкою НП, зміна статусу, **Скасувати/Повернути в роботу** (с подтверждением), ТТН НП, повернення, історія (`manager`-рядки пишет бэк); фільтри статус/джерело/оплата/пошук; опрос 30 с + терракотовый спалах новых + тост; `?order=` открывает карточку |
| Клієнти `/clients` | Картки (аватар-ініціал, імʼя окремо, телефон окремо `tel:`+копія, сегмент+температура) + **drawer**: сегмент-селект, температура (Авто/…), історія, перегляд/відправка (AI/шаблон), видалення + GDPR-erase (owner/admin); імпорт CSV (фиксированные колонки, 1000) |
| Вхідні `/inbox` | Діалоги + тред + відповідь (поле мертве без діалогу), канали/статусы через словарь, закрити/відкрити, «Взяти собі» |
| Завдання `/tasks` | Групи (Прострочені/Сьогодні/Завтра/Пізніше/Виконані), чекбокс + видалення (оптимистично), пріоритет іконка+текст, швидке створення |
| Товари `/products`,`/feedhub` | Джерела (статус іконка+текст, створення/видалення, Оновити з чесним `ok`), журнал, каталог |
| Аналітика `/analytics` | Период 7/30/90; KPI с лічильником (виручка/замовлення/AOV/ліди/конверсія/повтори/повернення); виручка-бары (вісь з нуля); лінія замовлень; воронка з % і сумами; факт+пунктир + сума; топ LTV + repeat; втрати + повернення; **RFM**; **прогноз діапазоном**; **AI «Наступні дії» + ризик відтоку**; 402 → банер, виручка видна |
| Інтеграції | Статус + `last_sync_at/last_error`, Синхронізувати + Тест (реальные вызовы), **майстер** (провайдер → ключ/JSON по подсказкам → перевірка → webhook-URL+секрет) |
| Налаштування `/settings` | Вигляд (тема + границы авто), анімації (на сервер), команда/безпека (ссылки), воронки (чтение), свої поля (CRUD), теги, **журнал змін** |
| Автоматизації `/automations` | «5 правил одним кліком» (идемпотентно), список + статистика, конструктор (11 тригеров × 7 дій), журнал (статус/дата/помилка) |
| Тариф `/billing` | Поточний (місця/сума/фічі), плани, апгрейд (LiqPay-форма / Mono-ссилка / людські 409/403), рахунки, запрошення (пароль показать коллеге) |
| Сповіщення `/notifications` | Redis-стрічка (эмодзи сервера чистятся, epoch → дата), опрос 30 с |
| Безпека `/password` | Смена пароля (отзывает сессии → разлогин — задумано), 2FA (QR-строка + код) |
| Вхід `/login` | Email+пароль+компанія+2FA, регистрация (подсказка про лимит пароля и письмо), токен подтверждения, автовход в Telegram Mini App |

---

## 6. Дизайн-система (обязательно для правок)

- Цвета только из токенов (`brand-tokens.css` — тёплая «Лелека»: крем/терракота;
  hex в `.tsx` запрещён, исключение — SVG/конфетти). Контраст проверяется
  резолвером (16 пар, было поймано 3.58 → исправлено).
- Темы «Ранок/Вечір»: `data-theme`, `auto-time` 07–19 Europe/Kyiv, anti-flash,
  сервер+кэш, Telegram-режим, View Transitions со сменой.
- `html[data-anim]` (`all/min/off`, с сервера; `prefers-reduced-motion` → min):
  `motion.css` — длительности 120–1200мс, только transform/opacity
  (переходы, шиммер, тосты, drawer, спалах, шаги+машинка, sway-лелека, press/shake/pulse, плейсхолдер, stagger-картки, hover-ліфт).
- Компоненты `ui.tsx` (+ `press`, `skeleton-shimmer`, лелека в EmptyState).
  Глобальный `box-sizing: border-box` (ловил overflow инпутов на 390px).
  Эмодзи запрещены; статус = цвет+иконка+текст; ≥12px; цели ≥40px; aria-labels.
- Угода ≠ Замовлення («Угода #…»).

---

## 7. Инфра

- **Dev**: db/redis наружу, api+worker+beat, volume с кодом.
- **Prod** (`docker-compose.prod.yml` + `Caddyfile`): всё закрыто кроме 80/443;
  `frontend` собирает кабинет+лендинг в том; Caddy: `Accept: text/html` → SPA,
  fetch → API по списку (`test_caddy_routes` следит), docs скрыты,
  секрет в логах redact + `log_skip /webhooks*`, остальное 404; bot — профиль.
- **CI** (блокирующий): backend — gitleaks(ставится)/`ruff==0.16.9`/pip-audit/
  compile/alembic/pytest/contrast; frontend — ci/tsc/build (main 381КБ +
  lazy Analytics); snapshots (postgres+redis, api, build, 24 кадра, артефакты).
- Скрипты: `snapshots.py` (регистрация чистого тенанта, 6 экранов, overflow+
  JS-ошибки = fail), `check-contrast.mjs`, `backup.sh` (cron 03:00, ротация 14).
- Лендинг: `frontend/public/about.html` (прод, без localhost/битых ссылок,
  факты вместо лозунгов, WebP ~65–169КБ вместо 520–780КБ) + `privacy.html`
  (бренд, TODO юрлица/почты для юриста); `frontend-preview/` — референс-прототип.

---

## 8. Проверено и история

| Проверка | Итог |
|---|---|
| `pytest` (env как в CI) | 92 passed, 4 skipped |
| `ruff` / `compileall` / `tsc` / `vite build` / contrast 16/16 / snapshots 24/24 | чисто |
| Изоляция: заказы/вхідні/інтеграції/повідомлення/пошук/види/тариф/audit + точечные | зелёные |
| 39 статичных вызовов фронта ↔ роуты, shapes ответов, TODO/консолі | 1-в-1 |

Проходы: (1) каркас/тариф/авторизация/темы; (2) drawers/автоматизации/тариф/
сповіщення/auth/DnD-pointer/motion; (3) тест-DB guard/вебхуки/sync/prod/CI/
contrast/лендинг/email-confirm/воркеры/кнопки/изоляция/снапшоты;
(4) редактирование угод/температура/undo-связей/DnD-ghost/fullscreen;
(5) shipments/actions/demo_seed-тесты, sync-хеш без позиции + даты,
Caddy Accept-маршрутизация (validate + тест), лимиты proxy+Redis,
CI ruff-пин, lazy Analytics (781→381КБ), WebP, aware `_now()`,
`enforce_password_change` удалён;
(6) недостающие кнопки готовых API (виды создать/применить, джерело фида,
импорт/erase клиентов, фильтры оплаты/поиска, «Взяти собі», токен confirm),
unlink-меню + дрібний клієнт на угодах, температура на картках.

---

## 9. Зазоры и roadmap (честно)

Открыто: массовые действия; менеджер диалога (есть «Взяти собі»); шаблоны
быстрых ответов; вкладки в drawer и друк; CSV/XLSX/PDF из UI; соцсети и
телефония; SSE вместо опроса; AI-чернетки; розсилки с согласиями; склад/ABC;
мультимагазин; публичный API; PWA; английский. Вручную на проде: реальный
ключ Prom → ТТН; живой платёж → вебхук; restore из бекапа (некопия, пока
не восстановлена); нагрузка 50×1000; юрист/юрлицо/почта; Lighthouse.
Известные quirks: бейдж сповіщень без «прочитано»; undo після конвертації
лишає замовлення; Rozetka `date_from` не отправляется (нет в задокументованому
API — sync останавливается по seen-набору); форматы дат провайдеров
нормализуются, но сверены только с фикстурами, не с живыми ответами.

---

## 10. Правила агента

- Перед кодом — этот файл + скилл (`leleka-ui` для фронта, `leleka-migrations`
  для схемы — только Alembic с downgrade + `schema.sql`).
- Одна задача; тесты зелёные до коммита; `.env`/ключи не коммитить; только
  тестовая БД (conftest страхует, но не уповай).
- Форматы провайдеров — только по официальной документации.
- Бэк: командой из §2 (обе URL тестовые). Фронт: `tsc + build (+contrast,
  snapshots при UI-правках)`.
