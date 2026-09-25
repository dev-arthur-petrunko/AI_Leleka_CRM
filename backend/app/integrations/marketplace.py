"""Prom / Rozetka: автопідтягування замовлень (п.2, п.4 плану).

Прод-флоу: маркетплейс -> POST /webhooks/{provider}?tenant=slug -> webhook_events
-> цей pull_orders (для первинного імпорту) -> clients + deals.
"""

from app.integrations.base import BaseAdapter


class PromAdapter(BaseAdapter):
    provider = "prom"

    def pull_orders(self, limit: int = 50) -> dict:
        if not self.configured:
            return self.stub("pull_orders", {"limit": limit})

        def _do():
            import requests
            r = requests.get("https://my.prom.ua/api/v1/orders/list",
                headers={"Authorization": f"Bearer {self.creds.get('token')}"},
                params={"limit": limit}, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        return self._call(_do)


class RozetkaAdapter(BaseAdapter):
    provider = "rozetka"

    def pull_orders(self, limit: int = 50) -> dict:
        if not self.configured:
            return self.stub("pull_orders", {"limit": limit})

        def _do():
            import requests
            r = requests.get("https://api-seller.rozetka.com.ua/orders/search",
                headers={"Authorization": f"Bearer {self.creds.get('token')}"},
                params={"limit": limit}, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        return self._call(_do)


def normalize_order(provider: str, raw: dict) -> dict:
    """Єдиний формат замовлення -> client + deal."""
    if provider == "prom":
        return {"external_id": str(raw.get("id", "")),
                "name": raw.get("client_first_name", "Клієнт Prom"),
                "phone": raw.get("client_phone", ""),
                "amount": float(raw.get("price", 0) or 0)}
    return {"external_id": str(raw.get("id", "")),
            "name": raw.get("customer", {}).get("name", "Клієнт Rozetka") if isinstance(raw.get("customer"), dict) else "Клієнт Rozetka",
            "phone": (raw.get("customer", {}) or {}).get("phone", "") if isinstance(raw.get("customer"), dict) else "",
            "amount": float(raw.get("amount", 0) or 0)}
