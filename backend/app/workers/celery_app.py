"""Celery: черга + планувальник (фаза 3.1). Старі cron-скрипти лишились
тонкими CLI-обгортками — логіка живе тут і в існуючих модулях."""

import os

from celery import Celery
from celery.schedules import crontab

celery = Celery("leleka",
                broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
                backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
celery.conf.update(task_acks_late=True, worker_prefetch_multiplier=1,
                   task_reject_on_worker_lost=True)

celery.conf.beat_schedule = {
    "webhooks-every-30s": {"task": "leleka.process_webhook_batch",
                           "schedule": 30.0},
    "sync-every-10m": {"task": "leleka.sync_due_integrations",
                       "schedule": crontab(minute="*/10")},
    "stuck-hourly": {"task": "leleka.run_stuck_check", "schedule": crontab(minute=5)},
    "feed-every-15m": {"task": "leleka.run_feed_scheduler",
                       "schedule": crontab(minute="*/15")},
    "np-poll-45m": {"task": "leleka.run_np_poll",
                    "schedule": crontab(minute="*/45")},
    "billing-monthly": {"task": "leleka.run_billing_recalc",
                        "schedule": crontab(day_of_month=1, hour=9, minute=0)},
}
