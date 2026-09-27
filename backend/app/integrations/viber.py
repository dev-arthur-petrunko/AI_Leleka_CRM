"""Viber: Business Messages API.

Важливо (платформне обмеження, не наше): щоб писати клієнту першим,
потрібен схвалений Viber Business акаунт (проходить модерацію Rakuten
Viber, це не миттєво як Telegram-бот) І viber_id клієнта — він теж
з'являється лише після того, як клієнт написав вам першим у Viber.
"""

from app.integrations.base import BaseAdapter


class ViberAdapter(BaseAdapter):
    provider = "viber"

    def send_message(self, viber_id: str, text: str) -> dict:
        if not self.configured:
            return self.stub("send_message", {"viber_id": viber_id, "text": text[:80]})

        def _do():
            import requests
            r = requests.post(
                "https://chatapi.viber.com/pa/send_message",
                headers={"X-Viber-Auth-Token": self.creds.get("auth_token")},
                json={"receiver": viber_id, "type": "text", "text": text,
                      "sender": {"name": self.creds.get("sender_name", "AI Leleka")}},
                timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        return self._call(_do)
