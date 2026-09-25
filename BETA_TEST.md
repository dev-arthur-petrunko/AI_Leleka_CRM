# Закритий бета-тест AI Leleka CRM (п.8 плану)

## 1. Підготовка (5 хв)
```bash
docker compose up --build
python -m app.workers.demo_seed --slug beta1
```
Логін: `owner@demo.ua / demo1234`, docs: `http://localhost:8000/docs`

## 2. Сценарії для 3-5 реальних ФОПів (7-14 днів)
1. **Новий лід**: POST /clients → перевірити автораунд-менеджера + automation_logs
2. **Зависла угода**: змінити last_activity_at на -4 дні → `python -m app.workers.stuck_checker --days 3` → задача менеджеру
3. **Оплата**: POST /integrations (novaposhta test) → stub ТТН
4. **Дашборд**: GET /analytics/dashboard → воронка, hot-10, прогноз
5. **Ліміти**: Free=1 місце → POST /billing/invite-check другим юзером → 402

## 3. Що збираємо (UX — головна причина втечі в Excel)
- Час створення угоди (ціль: <30 сек)
- Чи зрозумілий дашборд без навчання?
- Яких інтеграцій не вистачає? (Нова Пошта / Checkbox / Prom?)
- Чи довіряють audit_log? (показати «хто видалив»)

## 4. Критерій виходу в публіку
- 0 втрачених webhook_events (всі processed)
- automation success rate >95% (/automations/stats)
- 3+ бізнеси кажуть «зручніше за Excel»
