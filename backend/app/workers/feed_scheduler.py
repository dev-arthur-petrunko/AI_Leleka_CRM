"""Планувальник Feed Hub (запуск за розкладом через cron).

Кожні 15 хв: */15 * * * * cd /code && python -m app.workers.feed_scheduler
Шукає активні джерела, в яких last_run_at + interval_minutes минув, і проганяє.
Алерт про stale-фіди (>N годин без успішного рану) — у менеджерський інбокс.
"""

from datetime import datetime, timedelta, UTC

from app.db.session import SessionLocal
from app.models import FeedRun, FeedSource
from app.services import notify as notify_queue
from app.services.feedhub import run_source

STALE_HOURS = 6


def run_due() -> list[dict]:
    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        out = []
        for src in db.query(FeedSource).filter(FeedSource.is_active.is_(True)).all():
            due = (not src.last_run_at or
                   (src.last_run_at.replace(tzinfo=UTC)
                    + timedelta(minutes=src.interval_minutes) <= now))
            if due:
                out.append({"source": src.name, **run_source(db, src.id)})
        # stale-алерти
        for src in db.query(FeedSource).filter(FeedSource.is_active.is_(True)).all():
            ok_run = db.query(FeedRun).filter(
                FeedRun.source_id == src.id, FeedRun.status == "ok")\
                .order_by(FeedRun.started_at.desc()).first()
            last_ok = ok_run.started_at if ok_run else None
            if last_ok and last_ok.replace(tzinfo=UTC) < now - timedelta(hours=STALE_HOURS):
                notify_queue.push(src.tenant_id,
                                  f"⚠️ Фід «{src.name}» не оновлювався >{STALE_HOURS} год",
                                  kind="feed_stale", ref={"source_id": str(src.id)})
                out.append({"source": src.name, "stale_alert": True})
        return out
    finally:
        db.close()


if __name__ == "__main__":
    import json
    print(json.dumps(run_due(), ensure_ascii=False, indent=2, default=str))
