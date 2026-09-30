---
name: leleka-tenant-isolation
description: Use whenever adding or changing any API endpoint, query, worker or webhook handler in AI Leleka CRM that touches business tables (clients, deals, orders, tasks, integrations, webhook_events). Enforces multi-tenant isolation.
---
# Правила изоляции тенантов
1. Каждый запрос к бизнес-таблице содержит `Model.tenant_id == tenant_id`; tenant_id берётся ТОЛЬКО из JWT (`get_current_tenant`) или из проверенной интеграции. Никогда из body/query.
2. Каждый эндпоинт имеет явную зависимость: `get_current_user` / `require_role(...)`. Публичные эндпоинты перечислены в tests/test_public_endpoints.py.
3. Уникальные ключи всегда включают tenant_id: UNIQUE(tenant_id, ...).
4. Воркеры получают tenant_id явно и фильтруют по нему.
5. Для каждого нового эндпоинта добавь тест: пользователь тенанта B получает 404/403 на объект тенанта A.
6. Перед завершением: `pytest backend/tests -k tenant`.
