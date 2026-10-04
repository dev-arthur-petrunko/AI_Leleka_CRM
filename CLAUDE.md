# AI Leleka CRM — правила для агента
- Стек: FastAPI, PostgreSQL 16, Redis 7, Alembic, Docker Compose.
- Перед кодом прочитай docs/AGENT_PLAN.md (текущая фаза) и навыки из .claude/skills.
- Работай по одной задаче за раз; после каждой: тесты зелёные, коммит с понятным сообщением.
- Не трогай .env и секреты. Не коммить ключи. Не подключайся к боевой БД.
- Любое изменение схемы только через Alembic.
- Если что-то в плане противоречит коду, остановись и опиши расхождение, не угадывай.
- Запуск тестов: `docker compose exec -T -e DATABASE_URL=postgresql+psycopg2://leleka:leleka@db:5432/leleka_test api python -m pytest -q` (обидві URL на тестову БД, як у CI; спочатку `alembic upgrade head` з тим же DATABASE_URL).
- UI-фаза описана в docs/AGENT_PLAN_UI.md; навык leleka-ui обязателен для любого фронтенда.
