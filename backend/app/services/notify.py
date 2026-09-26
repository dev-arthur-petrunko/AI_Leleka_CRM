"""Інбокс сповіщень менеджера на Redis (черга з ТЗ).

_notify в actions сюди пушить; GET /notifications забирає.
Якщо Redis недоступний — повертаємо [] (задачі-бекап створює сам _notify).
"""

import json
import time
from uuid import UUID

import redis

from app.core.config import settings


def _client() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)


def push(tenant_id: UUID, text: str, kind: str = "notify",
         ref: dict | None = None) -> bool:
    try:
        _client().lpush(f"notif:{tenant_id}", json.dumps({
            "text": text, "kind": kind, "ref": ref or {},
            "ts": int(time.time()),
        }))
        _client().ltrim(f"notif:{tenant_id}", 0, 99)  # останні 100
        return True
    except Exception:
        return False


def pull(tenant_id: UUID, limit: int = 20) -> list[dict]:
    try:
        raw = _client().lrange(f"notif:{tenant_id}", 0, limit - 1)
        return [json.loads(x) for x in raw]
    except Exception:
        return []
