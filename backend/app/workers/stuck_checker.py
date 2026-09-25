"""Воркер «зависших угод». Запуск: python -m app.workers.stuck_checker.

В проде — Celery beat / APScheduler + Redis-очередь.
MVP: cron раз в час -> python -m app.workers.stuck_checker --days 3
"""

import argparse
from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.models import Deal, Tenant
from app.services.automation import run_automations


def check_stuck(days: int = 3) -> dict:
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stuck = db.query(Deal).filter(
            Deal.stage.notin_(["won", "lost"]),
            Deal.last_activity_at < cutoff,
        ).all()
        fired = 0
        for deal in stuck:
            run_automations(db, deal.tenant_id, "deal_stuck", {
                "deal_id": str(deal.id),
                "client_id": str(deal.client_id),
                "manager_id": str(deal.manager_id) if deal.manager_id else None,
                "stage": deal.stage,
                "amount": float(deal.amount or 0),
                "stuck_days": days,
            })
            fired += 1
        return {"stuck_found": len(stuck), "rules_fired_for": fired}
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=3)
    args = parser.parse_args()
    print(check_stuck(args.days))
