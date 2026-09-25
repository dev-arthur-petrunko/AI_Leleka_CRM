"""Сід демо-даних для закритого бета-тесту (п.8 плану).

Запуск: python -m app.workers.demo_seed --slug demo
Створює: tenant demo + owner + 2 менеджери + 10 клієнтів + угоди + правила.
"""

import argparse
import random

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import AutomationRule, Client, Deal, Tenant, User


def seed(slug: str = "demo"):
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
        if not tenant:
            tenant = Tenant(name="Демо Магазин", slug=slug, plan="pro")
            db.add(tenant)
            db.flush()
        if not db.query(User).filter(User.tenant_id == tenant.id).first():
            db.add(User(tenant_id=tenant.id, email="owner@demo.ua",
                        password_hash=hash_password("demo1234"),
                        full_name="Власник", role="owner"))
            for i in range(2):
                db.add(User(tenant_id=tenant.id, email=f"manager{i+1}@demo.ua",
                            password_hash=hash_password("demo1234"),
                            full_name=f"Менеджер {i+1}", role="manager"))
            db.flush()
        names = ["Олена", "Тарас", "Ірина", "Богдан", "Софія",
                 "Андрій", "Марія", "Петро", "Надія", "Олег"]
        stages = ["new", "contacted", "negotiation", "won", "lost"]
        managers = db.query(User).filter(User.tenant_id == tenant.id).all()
        for i, name in enumerate(names):
            c = Client(tenant_id=tenant.id, name=f"{name} (+3809700000{i:02d})",
                       phone=f"+3809700000{i:02d}", source=random.choice(["form", "prom", "manual"]),
                       segment=random.choice(["new", "regular", "vip"]),
                       assigned_to=random.choice(managers).id)
            db.add(c)
            db.flush()
            for _ in range(random.randint(1, 2)):
                st = random.choice(stages)
                db.add(Deal(tenant_id=tenant.id, client_id=c.id,
                            manager_id=c.assigned_to,
                            title=f"Замовлення #{random.randint(100,999)}",
                            amount=random.randint(500, 50000),
                            stage=st,
                            loss_reason="ціна" if st == "lost" else None))
        if not db.query(AutomationRule).filter(AutomationRule.tenant_id == tenant.id).first():
            db.add(AutomationRule(tenant_id=tenant.id, name="Новий лід -> менеджер",
                                  trigger_type="new_lead", action_type="assign_manager"))
        db.commit()
        return {"ok": True, "slug": slug, "login": "owner@demo.ua / demo1234"}
    finally:
        db.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--slug", default="demo")
    print(seed(p.parse_args().slug))
