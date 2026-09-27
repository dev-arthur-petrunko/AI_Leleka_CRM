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


def _product_summary(items: list) -> str | None:
    """Найкраще зусилля: список товарів -> короткий текстовий підсумок.

    Маркетплейси не гарантують однакову форму items, тож приймаємо
    що завгодно схоже на список і беремо назви, які знайдемо.
    """
    if not isinstance(items, list) or not items:
        return None
    names = [str(i.get("name") or i.get("title") or "").strip()
             for i in items if isinstance(i, dict)]
    names = [n for n in names if n]
    if not names:
        return None
    if len(names) == 1:
        return names[0]
    return f"{names[0]} та ще {len(names) - 1} поз."


def normalize_order(provider: str, raw: dict) -> dict:
    """Єдиний формат замовлення -> client + deal."""
    if provider == "prom":
        return {"external_id": str(raw.get("id", "")),
                "name": raw.get("client_first_name", "Клієнт Prom"),
                "phone": raw.get("client_phone", ""),
                "amount": float(raw.get("price", 0) or 0),
                "product_summary": _product_summary(raw.get("products", []))}
    customer = raw.get("customer") if isinstance(raw.get("customer"), dict) else {}
    return {"external_id": str(raw.get("id", "")),
            "name": customer.get("name", "Клієнт Rozetka"),
            "phone": customer.get("phone", ""),
            "amount": float(raw.get("amount", 0) or 0),
            "product_summary": _product_summary(raw.get("items", []))}
