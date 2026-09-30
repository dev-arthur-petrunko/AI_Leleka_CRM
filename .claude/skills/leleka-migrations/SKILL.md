---
name: leleka-migrations
description: Use when changing database models or schema in AI Leleka CRM (Alembic migrations).
---
# Правила миграций
1. Схему меняет ТОЛЬКО Alembic. `db/schema.sql` регенерируется после миграций.
2. Одна миграция = одно логическое изменение; всегда есть `downgrade()`.
3. Новые NOT NULL колонки на существующих таблицах: сначала nullable + backfill, потом NOT NULL отдельной миграцией.
4. Проверка: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` на чистой БД.
5. Индексы начинаются с tenant_id: (tenant_id, created_at), (tenant_id, status).
