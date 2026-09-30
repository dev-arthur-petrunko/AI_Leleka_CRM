---
name: leleka-integration-adapter
description: Use when adding or modifying an external integration (marketplace, shop platform, delivery, payment, messenger) in AI Leleka CRM.
---
# Как добавлять интеграцию
1. Адаптер наследует `BaseAdapter` (backend/app/integrations/base.py). Методы: `test()`, `pull_orders(since_cursor)`, `normalize_order(raw) -> OrderDTO`.
2. Ключи хранятся только через `encrypt_credentials`; в логах и ответах API ключей нет.
3. Импорт идемпотентен: upsert по UNIQUE(tenant_id, source, external_id); повторный запуск не создаёт дублей.
4. Телефоны проходят через `normalize_phone()`.
5. Сеть: таймаут, ретраи с экспоненциальной паузой, уважение к rate-limit провайдера (HTTP 429).
6. Тесты работают на записанных ответах провайдера (fixtures в tests/fixtures/<provider>/), без реальной сети.
7. Формат API провайдера сверяй с его официальной документацией, не по памяти.
