"""LiqPay + Monobank Acquiring: оплата + інвойс (п.4 плану)."""

import base64
import hashlib
import json

from app.integrations.base import BaseAdapter


class LiqPayAdapter(BaseAdapter):
    provider = "liqpay"

    def invoice_link(self, amount: float, order_id: str, description: str = "Оплата") -> dict:
        if not self.configured:
            return self.stub("invoice_link", {"amount": amount, "order_id": order_id})
        pub, priv = self.creds.get("public_key"), self.creds.get("private_key")
        params = {"public_key": pub, "version": "3", "action": "invoice",
                  "amount": amount, "currency": "UAH",
                  "description": description, "order_id": order_id}
        data = base64.b64encode(json.dumps(params).encode()).decode()
        sign = base64.b64encode(
            hashlib.sha1((priv + data + priv).encode()).digest()).decode()
        return {"ok": True, "stub": False, "data": data, "signature": sign,
                "pay_url": f"https://www.liqpay.ua/api/3/checkout?data={data[:20]}..."}


class MonoAdapter(BaseAdapter):
    provider = "monobank"

    def create_invoice(self, amount_uah: float, webhook_url: str = "") -> dict:
        if not self.configured:
            return self.stub("create_invoice", {"amount": amount_uah})

        def _do():
            import requests
            r = requests.post("https://api.monobank.ua/api/merchant/invoice/create",
                headers={"X-Token": self.creds.get("token")},
                json={"amount": int(amount_uah * 100),
                      "redirectUrl": webhook_url}, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        return self._call(_do)
