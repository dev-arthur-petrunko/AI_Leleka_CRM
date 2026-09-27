"""Щомісячний перерахунок per-seat білінгу (запуск за розкладом).

Оренда місць змінюється (запрошення/деактивації), а рахунок фіксується
при апгрейді — цей воркер знаходить розбіжності і звітує, що донарахувати.

Запуск вручну: python -m app.workers.billing_recalc
Cron (прод, 1-го числа о 09:00): 0 9 1 * * cd /code && python -m app.workers.billing_recalc
Прод-наступний крок: замість звіту — авто-створення BillingOrder(pending) + інвойс.
"""

from app.db.session import SessionLocal
from app.models import BillingOrder, Tenant, User
from app.services.billing import PLANS


def recalc() -> list[dict]:
    db = SessionLocal()
    try:
        out = []
        tenants = db.query(Tenant).filter(
            Tenant.plan != "free", Tenant.status == "active").all()
        for t in tenants:
            seats_now = db.query(User).filter(
                User.tenant_id == t.id, User.is_active.is_(True)).count()
            last = db.query(BillingOrder).filter(
                BillingOrder.tenant_id == t.id, BillingOrder.status == "paid")\
                .order_by(BillingOrder.paid_at.desc()).first()
            seats_billed = last.seats_billed if last else 0
            price = PLANS.get(t.plan, {}).get("price_uah", 0)
            delta = seats_now - seats_billed
            out.append({"tenant": t.slug, "plan": t.plan, "seats_now": seats_now,
                        "seats_billed": seats_billed, "delta": delta,
                        "adjust_uah": delta * price,
                        "action": "донарахувати" if delta > 0 else (
                            "повернути/зарахувати" if delta < 0 else "ок")})
        return out
    finally:
        db.close()


if __name__ == "__main__":
    import json
    print(json.dumps(recalc(), ensure_ascii=False, indent=2))
