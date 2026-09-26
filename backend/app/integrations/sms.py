"""SMS-провайдери: SendPulse / TurboSMS (українська специфіка).

Прод-флоу: ключ у integrations(provider='sendpulse'|'turbosms') ->
_send_message в actions викликає цей адаптер. Без ключа — чесний stub.
"""

from app.integrations.base import BaseAdapter


class SendPulseAdapter(BaseAdapter):
    provider = "sendpulse"

    def send_sms(self, to: str, text: str) -> dict:
        if not self.configured:
            return self.stub("send_sms", {"to": to, "text": text[:80]})

        def _do():
            import requests
            r = requests.post("https://api.sendpulse.com/oauth/access_token",
                json={"grant_type": "client_credentials",
                      "client_id": self.creds.get("client_id"),
                      "client_secret": self.creds.get("client_secret")},
                timeout=self.timeout)
            r.raise_for_status()
            token = r.json().get("access_token")
            r2 = requests.post("https://api.sendpulse.com/sms/send",
                headers={"Authorization": f"Bearer {token}"},
                json={"phones": [to], "body": text,
                      "sender": self.creds.get("sender", "Leleka")},
                timeout=self.timeout)
            r2.raise_for_status()
            return r2.json()
        return self._call(_do)


class TurboSmsAdapter(BaseAdapter):
    provider = "turbosms"

    def send_sms(self, to: str, text: str) -> dict:
        if not self.configured:
            return self.stub("send_sms", {"to": to, "text": text[:80]})

        def _do():
            import requests
            r = requests.post("https://api.turbosms.ua/message/send.json",
                headers={"Authorization": f"Bearer {self.creds.get('token')}"},
                json={"recipients": [to], "sms": {
                    "sender": self.creds.get("sender", "Leleka"), "text": text}},
                timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        return self._call(_do)
