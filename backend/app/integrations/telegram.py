"""Telegram: надсилання повідомлень клієнту через Bot API.

Важливо (не технічне обмеження, а платформне): бот може написати
клієнту, ТІЛЬКИ якщо клієнт раніше сам почав діалог з ботом (натиснув
Start або написав першим). Тому Client.telegram_chat_id — не те, що
можна "просто дізнатись" за номером телефону; він з'являється лише
після того, як клієнт хоч раз написав вашому бізнес-боту.
"""

from app.integrations.base import BaseAdapter


class TelegramAdapter(BaseAdapter):
    provider = "telegram"

    def send_message(self, chat_id: str, text: str) -> dict:
        if not self.configured:
            return self.stub("send_message", {"chat_id": chat_id, "text": text[:80]})

        def _do():
            import requests
            token = self.creds.get("bot_token")
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        return self._call(_do)
