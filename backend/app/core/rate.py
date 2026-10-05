"""Єдиний rate-limiter на весь app (щоб уникнути циклічних імпортів)."""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# Лічильники в Redis (спільні для всіх воркерів uvicorn), при його падінні —
# памʼять (in_memory_fallback), щоб ліміти не клали API. Без REDIS_URL — memory.
# За проксі (Caddy) справжній IP береться з X-Forwarded-For — див. --proxy-headers
# у compose (довіряємо лише мережі Docker, порти api назовні не світяться).
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"],
    storage_uri=os.environ.get("REDIS_URL", "memory://"),
    in_memory_fallback_enabled=True,
)
