# -*- coding: utf-8 -*-
"""Єдиний узгоджений демо-набір (UI 6.1): клієнти, угоди, замовлення, задачі, діалоги.
Уся аналітика рахується з нього. Демо лише з DEMO_MODE=1 або ?demo=1 (плашка «Демо-дані»).

Запуск: cd backend && python -m scripts.seed_demo [--force]
"""

import argparse
import os
import random
from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (Client, Conversation, Deal, Message, Order, Task, Tenant,
                        User)

SLUG = "demo"
# UI-18: детермінованість — фіксоване зерно і фіксована «сьогодні» в демо-режимі
random.seed(42)
DEMO_NOW = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)


def seed(force: bool = False):
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.slug == SLUG).first()
        if tenant and not force:
            return {"ok": True, "slug": SLUG, "existed": True}
        if tenant and force:
            db.query(Task).filter(Task.tenant_id == tenant.id).delete()
            db.query(Message).filter(Message.tenant_id == tenant.id).delete()
            db.query(Conversation).filter(Conversation.tenant_id == tenant.id).delete()
            db.query(Order).filter(Order.tenant_id == tenant.id).delete()
            db.query(Deal).filter(Deal.tenant_id == tenant.id).delete()
            db.query(Client).filter(Client.tenant_id == tenant.id).delete()
            db.commit()
        if not tenant:
            tenant = Tenant(name="Демо Магазин", slug=SLUG, plan="pro")
            db.add(tenant)
            db.flush()
            owner = User(tenant_id=tenant.id, email="demo@demo.ua",
                         password_hash=hash_password("Demo123456"),
                         full_name="Власник", role="owner", email_confirmed=True)
            db.add(owner)
            db.flush()
        now = DEMO_NOW if os.environ.get("DEMO_MODE") == "1" else datetime.now(timezone.utc)
        clients = []
        for name, phone, seg in [("Олена", "+380501111111", "vip"),
                                 ("Тарас", "+380502222222", "regular"),
                                 ("Петро", "+380503333333", "new")]:
            c = Client(tenant_id=tenant.id, name=name, first_name=name,
                       phone=phone, source="form", segment=seg)
            db.add(c)
            db.flush()
            clients.append(c)
        deals = [
            ("Угода #1", clients[0].id, 40000, "negotiation", 0),
            ("Угода #2", clients[1].id, 20000, "contacted", 1),
            ("Угода #3", clients[2].id, 10000, "new", 2),
            ("Угода #4", clients[0].id, 50000, "won", 30),
        ]
        for title, cid, amount, stage, days_ago in deals:
            db.add(Deal(tenant_id=tenant.id, client_id=cid, title=title,
                        amount=amount, stage=stage,
                        last_activity_at=now - timedelta(days=days_ago),
                        won_at=now - timedelta(days=days_ago) if stage == "won" else None))
        o1 = Order(tenant_id=tenant.id, client_id=clients[0].id, source="prom",
                   external_id="P-1", order_number="A-1", status="delivered",
                   payment_status="paid", total=40000, placed_at=now - timedelta(days=10))
        o2 = Order(tenant_id=tenant.id, client_id=clients[1].id, source="manual",
                   external_id="M-1", order_number="A-2", status="new",
                   payment_status="unpaid", total=20000, placed_at=now - timedelta(days=1))
        db.add_all([o1, o2])
        db.add(Task(tenant_id=tenant.id, title="Передзвонити Петру",
                    due_at=now - timedelta(days=1), status="open", priority="high"))
        db.add(Task(tenant_id=tenant.id, title="Надіслати рахунок",
                    due_at=now + timedelta(days=1), status="open"))
        conv = Conversation(tenant_id=tenant.id, client_id=clients[0].id,
                            channel="telegram", last_message_at=now)
        db.add(conv)
        db.flush()
        db.add(Message(tenant_id=tenant.id, conversation_id=conv.id,
                       direction="in", channel="telegram", body="Добрий день!",
                       external_id="demo-m1"))
        db.commit()
        return {"ok": True, "slug": SLUG, "login": "demo@demo.ua / Demo123456"}
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    print(seed(ap.parse_args().force))
