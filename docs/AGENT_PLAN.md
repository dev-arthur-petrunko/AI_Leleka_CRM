# AI Leleka CRM — актуальное состояние проекта

> Переписано по факту кода на октябрь 2026 (коммитов: 65+, `main`).
> Старый план по фазам 0–8 остался в истории git; этот файл — описание того,
> **что реально есть**, как запускать, как устроен дизайн и что осталось.
> Если что-то здесь противоречит коду — верь коду и поправь файл.

---

## 1. Что это

SaaS-CRM для украинского интернет-магазина: заказы с Prom/Rozetka/сайта,
Нова Пошта, касса и оплата, Telegram и AI — в одном месте.
Позиционирование: настройка за 15 минут, гривна, Telegram-first.

**Стек (факт):**

| Слой | Технологии |
|---|---|
| API | FastAPI 0.115, SQLAlchemy 2.0, Pydantic 2.9, Alembic 1.13 |
| БД / очередь | PostgreSQL 16, Redis 7, Celery 5.4 (worker + beat) |
| Фронт | Vite 5 + React 18 + TypeScript 5, TanStack Query, Recharts, lucide-react |
| Бот | aiogram 3 (digest-уведомления, `/start` с deep-link) |
| Инфра | Docker Compose (dev + prod), GitHub Actions CI, Caddy-заглушка в prod |

---

## 2. Запуск (проверено живьём)

### Dev

```bash
cp backend/.env.example backend/.env
# в .env: SECRET_KEY (openssl rand -hex 32), CREDENTIALS_KEY (Fernet generate_key)
docker compose up --build -d
# API: http://localhost:8000/docs, фронт: cd frontend && npm i && npm run dev
```

Сервисы dev: `db` (5432 наружу), `redis` (6379 наружу), `api`
(`alembic upgrade head && uvicorn --reload`, 8000), `worker`, `beat`.

### Тесты (бэкенд, 64 шт — зелёные)

```bash
# ВАЖНО: обе переменные указывают на ОДНУ тестовую БД (как в CI),
# иначе тест воркера test_webhook_batch_dead_after_10 упадёт:
# воркер читает через SessionLocal (DATABASE_URL), а фикстуры — через TEST_DATABASE_URL.
docker compose exec -T -e DATABASE_URL=postgresql+psycopg2://leleka:leleka@db:5432/leleka_test \
  api alembic upgrade head
docker compose exec -T -e DATABASE_URL=postgresql+psycopg2://leleka:leleka@db:5432/leleka_test \
  api python -m pytest -q
# → 64 passed
```

`TEST_DATABASE_URL` уже прописан в `docker-compose.yml` (тестовая БД `leleka_test`,
conftest создаёт её сам). После изменения `backend/requirements.txt` обязательно
`docker compose build api worker beat` — иначе в образе старые зависимости
(так было: в образе не хватало pytest/httpx/celery и тесты вообще не стартовали).

### Фронт

```bash
cd frontend && npm i && npx tsc --noEmit && npm run build
# → чисто, dist/ собирается. Тестов фронта нет (только check-contrast, см. §8).
```

### Прод

`docker-compose.prod.yml`: БД/Redis без внешних портов, `uvicorn --workers 2`,
healthcheck у api **и** у db, секреты только из env. Бекап: `scripts/backup.sh`.

---

## 3. Бэкенд: карта (факт из `backend/app`)

`GET /health` — публичный. Коды: 401 — битый JWT (`core/deps.py`),
402 — платная фича (`require_plan_feature`: `ai_analytics` на всём `/analytics`,
провайдеры в `/integrations` через `_gate`), 403 — роль/подпись, 429 — slowapi.
Каждый ответ несёт `X-Request-ID`.

| Роутер | Префикс | Что умеет |
|---|---|---|
| `auth` | `/auth` | register/login/invite/2FA (pyotp)/refresh/reset/telegram |
| `clients` | `/clients` | CRUD, импорт CSV, interactions, `DELETE /{id}/erase` (обезличивание) |
| `messages` | `/clients` | `/{id}/message`, `/{id}/message-preview` (тот же префикс — коллизии нет: подпути разные) |
| `deals` | `/deals` | список (фильтры `stage`, `manager_id`), создание, `/export`, `/stuck`, `PATCH /{id}/stage` (причина програшу обязательна), `POST /{id}/convert-to-order` (идемпотентно) |
| `orders` | `/orders` | список/карточка/статусы/ТТН/возвраты, ручное создание, импорт CSV, `/export`, `/tags/*`, `/custom-fields`, `/pipelines` |
| `tasks` | `/tasks` | CRUD, просрочка |
| `webhooks` | `/webhooks` | `POST /{provider}/{integration_id}` с HMAC/секретом, `UNIQUE(tenant_id, provider, external_id)` |
| `automations` | `/automations` | правила «если → то», логи |
| `analytics` | `/analytics` | kpi/funnel/hot-leads/forecast/churn/loss-reasons/next-actions/dashboard (платно: `ai_analytics`) |
| `shop` | `/analytics/shop` | revenue/ltv/rfm/returns/forecast-range — **без paywall** (базовые метрики бесплатны) |
| `billing` | `/billing` | per-seat, LiqPay/Mono вебхуки с проверкой подписи; без PLATFORM-ключей апгрейд = 409 |
| `integrations` | `/integrations` | CRUD, `/{p}/test`, `/{p}/import-orders`, `/{p}/webhook-url`, статусы `ok/error/auth_failed`, `last_sync_at` |
| `feedhub` | `/feedhub` | sources/runs/products (YML-фиды) |
| `inbox` | `/inbox` | диалоги/треды/ответы; входящие Telegram через бота |
| `forms` | `/api/v1/forms` + `/forms` | публичный приём заявок (honeypot + rate-limit) |
| `notifications` | `/notifications` | уведомления API (экрана во фронте пока нет) |
| `search` | `/search`, `/today` | глобальный поиск + агрегат «Що зробити зараз» |
| `views` | `/views` | сохранённые фильтры (`saved_views`) |

Схема: 30+ таблиц, 11 миграций Alembic, HEAD `d1e2f3a4b5c6_ui_backend`
(`users.preferences`, `deals.converted_order_id`, `saved_views`). Все downgrade на месте.

Безопасность: tenant из JWT, изоляция `tenant_id` в каждом запросе (+ тест),
credentials только Fernet-шифрованные, телефоны через `normalize_phone`,
`SECRET_KEY < 32` — app не стартует (так задумано), старые дефолты скомпрометированы.

---

## 4. Фронт: карта (`frontend/src`)

Корень `/` — **Головна (Today)**, не Dashboard (`pages/Dashboard.tsx` — legacy,
из Routes удалён, файл оставлен как референс).

| Экран | Роут | Данные | Состояния |
|---|---|---|---|
| Головна | `/` | `GET /today` — группы «Прострочені / Нові замовлення / Без руху / Непрочитані» + привітання за часом доби + чек-лист «Старт за 5 хвилин» | Skeleton / Empty / Error — да |
| Угоди | `/deals` | канбан (нативный HTML5 DnD — `@dnd-kit` **нет**) + таблиця, «Мої» через `manager_id`, створення угод (клієнт+назва+сума), конвертація в замовлення, причина програшу | да |
| Замовлення | `/orders` | картки + **drawer картки**: позиції, лінія кроків статусу, зміна статусу, створення ТТН НП, повернення, історія, скасування/повернення в роботу; опитування кожні 30 с + спалах нових | да |
| Клієнти | `/clients` | картки + **drawer**: історія спілкування, перегляд/відправка листа (AI/шаблон), зміна сегмента, видалення | да |
| Вхідні | `/inbox` | діалоги + тред + відповідь (поле заблоковано без діалогу) | да (+ «Оберіть діалог») |
| Завдання | `/tasks` | групи Прострочені/Сьогодні/Завтра/Пізніше/Виконані, пріоритет = іконка+текст, швидке створення | да |
| Товари | `/products`, `/feedhub` | джерела фідів + журнал + каталог, кнопка «Оновити» | да |
| Аналітика | `/analytics` | KPI-ряд з лічильником, виручка-бары (вісь з нуля), замовлення-лінія, воронка з %, прогноз факт+пунктир, топ LTV, втрати/повернення, **RFM-сегменти, прогноз діапазоном**; при 402 — банер про тариф, виручка показується | да |
| Інтеграції | `/integrations` | статус іконка+текст, `last_sync_at/last_error`, «Синхронізувати» + «Тест», **майстер: провайдер → ключ → перевірка → адреса вебхука** | да |
| Налаштування | `/settings` | тема, анімації (на сервер), «я», **воронки, свої поля (CRUD), теги, журнал змін**, посилання на команду/безпеку | Skeleton/Error |
| Автоматизації | `/automations` | **«5 правил одним кліком» (seed-defaults)**, список + статистика спрацювань, конструктор правило (тригер→дія), журнал | да |
| Тариф | `/billing` | плани, поточний, апгрейд (409/403 по-людськи), **запрошення в команду з тимчасовим паролем** | да |
| Сповіщення | `/notifications` | стрічка з Redis-інбоксу, опитування 30 с; дзвіночок у шапці з бейджем | да |
| Безпека | `/password` | зміна пароля, 2FA (QR + код); примус при `must_change_password` | — |
| Вхід | `/login` | email + пароль + **компанія + 2FA-код**, реєстрація компанії, **автовхід у Telegram Mini App** | — |
| UI-kit | `/ui-kit` | демо компонентів (не для продакшена) | — |

API-клиент (`api.ts`): `HttpError(status)` на любой не-OK (кроме 401 → refresh-токен
один раз, потім чистка токенів і редирект на логін); `error` из useQuery реально
сетится, экраны показывают `ErrorState` с «Повторити». Таймаут 8 с.

---

## 5. Дизайн-система (факт, обязательно для любых правок)

- **Токены — единственный источник цвета.** База в `styles/tokens.css`,
палитра в `styles/brand-tokens.css` (тёплая «Лелека»: крем, терракота, очерет).
Hex в `.tsx` запрещён (исключение — SVG-градиенты и частицы конфетти как графика).
- **Темы «Ранок» / «Вечір»**: `data-theme` на `<html>`, режимы
`auto-time (07:00–19:00, Europe/Kyiv) / morning / evening / system / telegram`,
anti-flash скрипт в `index.html`, сохранение в `users.preferences` + localStorage-кэш.
- **Каркас**: ≥1024px — сворачиваемая боковая рейка (Ctrl+B) с бейджами;
<1024px — нижнее меню из 5 иконок (Головна, Угоди, Замовлення, Вхідні, Ще);
верхняя панель: крошки, поиск Ctrl+K, «+ Створити», тема. Контейнер ≤1440px.
- **Компоненты** (`components/ui.tsx`): Button / Input / Select / Checkbox /
Badge (тон+текст) / Card (`glass`) / Skeleton / EmptyState (с действием) /
ErrorState (с «Повторити») / Tabs. Иконки — только `lucide-react`, эмодзи в UI запрещены.
- **Подписи** — только через `i18n/uk.json` (`stage.*`, `order.*`, `pay.*`,
`source.*`, `segment.*`, `score.*`, `prio.*`, `feed.*`, `ch.*`, `conv.*`, `theme.*`).
Сырые коды (`negotiation`, `prom`, `hot`) пользователю не показываются.
- **Сущности не путать**: карточки угод — «Угода #…», чек — «Замовлення».
- **Демо**: только явное (`?demo=1` / `DEMO_MODE`) с плашкой «Демо-дані»; молчаливых
моков при ошибке API нет — есть баннер/состояние ошибки.
- **Статус = цвет + иконка + текст**; текст ≥12px; цели нажатия ≥40px на телефоне;
`aria-label` у иконок-кнопок; `prefers-reduced-motion` глушит анимации.
- **Анімації — `styles/motion.css`**: тривалості `--dur-120/150/200/320/600/1200`
і `--ease-out`; тільки transform/opacity; переходи сторінок 150мс, скелетон-шимер,
лічильники, тости, drawer, спалах нового замовлення, лінія кроків + машинка НП,
View Transitions для теми, sway-лелека в пустих станах, press/shake/pulse.
`html[data-anim]` керує всім (`all/min/off`, з сервера), `prefers-reduced-motion`
глобально глушить. Виграш — неблокувальний тост; повний екран лише від 50 000 ₴.

---

## 6. Инфра и смежное

- **CI** (`.github/workflows/ci.yml`): Postgres+Redis services, install,
`compileall`, `alembic upgrade head`, `pytest -q`, `check-contrast`.
`ruff`, `gitleaks`, `pip-audit` — стоят, но с `|| true` (не блочат).
- **Бот** (`bot/`): aiogram 3, `BOT_TOKEN` обязателен; утренний/вечерний дайджест —
пока лог-заглушка; в compose сервиса `bot` **нет** (запуск вручную).
- **Воркеры**: `process_webhook_batch` (SKIP LOCKED, backoff `min(2^n,60м)`, dead
после 10 попыток), sync по курсору, НП-трекінг, stuck, білінг, фіди.
- **Доки**: `AGENT_PLAN_UI.md` (каркас/темы/экраны — выполнено),
`AGENT_PLAN_UI_BRAND.md` (тёплая палитра победила — выполнено),
`AGENT_PLAN_LANDING.md` (аудит лендинга), `brand.md`, `landing-claims.md`,
`BETA_TEST.md` (**устарел**: только API-сценарии, про React-фронт ни слова).

---

## 7. Проверено живьём (октябрь 2026)

| Проверка | Результат |
|---|---|
| `docker compose ps` | 5/5 Up: api, db (healthy), redis, worker, **beat** (был остановлен — поднят) |
| `GET /health` | `{"ok":true}` |
| `pytest -q` (env как в CI) | **69 passed** |
| `ruff check backend` + `compileall` | чисто |
| `tsc --noEmit` + `vite build` | чисто, `built in ~7s` |
| Тест изоляции тенантов / публичных endpoints | зелёные |

**Исправлено в ходе ревизии:** образы пересобраны (не хватало pytest/httpx/celery);
`TEST_DATABASE_URL` добавлен в compose; поднят beat; `tags_router`-пустышка удалён;
`@app.on_event` → `lifespan`; healthcheck db в prod; `api.ts` бросает `HttpError`
(401/402/403 больше не молчат); `Analytics loading` — `||`; «Мої» в угодах работает
через `manager_id`; создание угод — диалогом (был `alert`); кнопка «Тест» интеграций
вызывает API (была мёртвой); мёртвые Bell/ThemeToggle/MOBILE/Dashboard-импорт убраны;
логотип бандлится импортом (был 404); эмодзи/hex в UI вычищены;
`SettingsConfigDict` вместо deprecated `class Config`.

---

## 8. Известные зазоры (не баги, но знать)

1. `check-contrast` всегда SKIP: токены ссылаются на `brand-tokens.css` через
`var()`, скрипт ждёт hex — проверка vacuous, но зелёная.
2. Воркер использует только `SessionLocal` — тесты обязаны гнать с
`DATABASE_URL == TEST_DATABASE_URL` (§2), иначе 1 красный.
3. Бандл ~700 КБ (recharts+framer-motion), чанк-варнинг Vite; code-splitting не настроен.
4. ~20k warnings в pytest: `jose.utcnow()` deprecated + pydantic-ворнинги — шум, не ошибки.
5. `ruff/gitleaks/pip-audit` в CI не блочат (`|| true`).
6. `/analytics/shop/*` без paywall — решение: базовые метрики бесплатны, AI — платно.
7. Фронт-тестов нет (ни unit, ни Playwright-снапшотов 390/1280 — скрипты не заведены).
8. Бота нет в compose; уведомлений-экрана нет (только API).
9. `BETA_TEST.md` устарел; `Dashboard.tsx` — legacy.

---

## 9. Что осталось (честно)

- [ ] Налаштування как экраны: ~~команда/роли (invite), воронки, шаблоны,~~ тариф/оплата — сейчас заглушки текстом.
  Готово: команда (invite), воронки (читання), свої поля, теги, пароль/2FA, журнал змін.
- [ ] Карточки заказа/клиента как drawer с вкладками (позиции, ТТН, історія, листування).
  Частково готово: обидва drawer є (позиції/ТТН/повернення/історія; листування/шаблони/відправка).
  Немає вкладок і друку накладних.
- [ ] Массовые действия в заказах, сохранённые виды в сделках (API `/views` есть, UI чипа-названия минимальны).
- [ ] Inbox: назначение менеджера, шаблоны быстрых ответов, статусы доставки.
- [ ] Экспорт CSV/XLSX из UI (API `/export` есть), PDF-отчёт по расписанию.
- [ ] Соц-каналы (Instagram/Facebook/WhatsApp), телефония — по спросу.
- [ ] Бот в compose + реальные дайджесты. Готово: экран уведомлений + бейдж.
- [ ] Realtime: зараз опитування 30 с (замовлення, сповіщення); справжні SSE/WebSocket — пізніше.
- [ ] ИИ-помощник у «Вхідні» (чернетка по контексту), розсилки по RFM (зі згодами), склад/маржа/ABC,
  кілька магазинів, кошики, календар задач, друк документів, публічний API, PWA, дзвінки, англійська.
- [ ] Фронт-тесты + Playwright-снапшоты + настоящий contrast-check по резолвленным токенам.
- [ ] Затянуть `ruff/gitleaks/pip-audit` в CI в blocking; code-splitting бандла.
- [ ] Юрблок фазы 8 (privacy/oferta/erase-flow) + нагрузочный тест + восстановление из бекапа.
- [ ] Обновить `BETA_TEST.md` под React-фронт; удалить `Dashboard.tsx` или вернуть как `/dashboard`.

---

## 10. Правила для агента (коротко, детали — `CLAUDE.md`, навыки — `.claude/skills/`)

- Перед кодом — этот файл + нужный скилл (`leleka-ui` для фронта обязателен).
- Одна задача за раз; тесты зелёные до коммита; схема — только Alembic с downgrade.
- Не трогать `.env`/секреты, не коммитить ключи, только тестовая БД.
- Не угадывать формат провайдеров — сверять с официальной документацией.
- Тесты бэка — командой из §2 (обе URL на тестовую БД!); фронт — `tsc + build`.
- После UI-правок: снапшоты 390/1280 в обеих темах (когда появятся скрипты).
