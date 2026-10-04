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
        """Обгортка з ретраями (retry) для нестабільної мережі.
        429 поважаємо: спимо Retry-After (до 30 с) і НЕ лупимо далі дарма."""
        last_err = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return {"ok": True, "data": fn(*args, **kwargs),
                        "attempt": attempt, "stub": False}
            except Exception as e:
                last_err = str(e)
                wait = min(2 ** attempt, 8)
                resp = getattr(e, "response", None)
                status = getattr(resp, "status_code", 0) if resp is not None else 0
                if status == 429 or "429" in last_err:
                    try:
                        ra = float((resp.headers.get("Retry-After", "0") if resp is not None else "0") or 0)
                    except (TypeError, ValueError):
                        ra = 0
                    wait = min(max(wait, ra), 30)
                    last_err = f"429 rate limited (retry_after={ra}s): {last_err}"
                time.sleep(wait)
        return {"ok": False, "error": last_err,
                "attempt": self.max_retries, "stub": False}

    def stub(self, action: str, payload: dict) -> dict:
        """Без ключів — повертаємо stub щоб MVP не падав на демо."""
        return {"ok": True, "stub": True, "action": action,
                "message": f"[{self.provider}] stub: додайте ключ в integrations",
                "payload": payload}
