"""Базовий клас адаптера: ретраї + логування + режим stub без ключів."""

import time


class BaseAdapter:
    provider: str = "base"
    timeout: int = 15
    max_retries: int = 3

    def __init__(self, credentials: dict, settings: dict | None = None):
        self.creds = credentials or {}
        self.settings = settings or {}

    @property
    def configured(self) -> bool:
        return bool(self.creds)

    def _call(self, fn, *args, **kwargs):
        """Обгортка з ретраями (retry) для нестабільної мережі."""
        last_err = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return {"ok": True, "data": fn(*args, **kwargs),
                        "attempt": attempt, "stub": False}
            except Exception as e:  # noqa: BLE001
                last_err = str(e)
                time.sleep(min(2 ** attempt, 8))
        return {"ok": False, "error": last_err,
                "attempt": self.max_retries, "stub": False}

    def stub(self, action: str, payload: dict) -> dict:
        """Без ключів — повертаємо stub щоб MVP не падав на демо."""
        return {"ok": True, "stub": True, "action": action,
                "message": f"[{self.provider}] stub: додайте ключ в integrations",
                "payload": payload}
