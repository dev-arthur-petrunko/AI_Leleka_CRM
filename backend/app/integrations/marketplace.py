"""Prom / Rozetka: автопідтягування замовлень.

Джерела формату (перевірено 2026-09-30):
- Prom: https://my.prom.ua/api/v1/docs, https://public-api.docs.prom.ua —
  база https://my.prom.ua/api/v1, `Authorization: Bearer <token>` (токен з кабінету,
  «Налаштування → Управління API-токенами»), GET /orders/list (status, date_from, limit),
  GET /orders/{id}, POST /orders/set_status.
- Rozetka Seller API: Bearer-токен продавця (протухає → потрібне оновлення;
  зауважено як ризик, механізм refresh — за фактом відповіді API).

Прод-флоу: polling (sync_state) — основний шлях; вебхуки — прискорювач.
"""

from app.integrations.base import BaseAdapter


class PromAdapter(BaseAdapter):
    provider = "prom"

    def pull_orders(self, limit: int = 50, date_from: str | None = None,
                    status: str | None = None) -> dict:
        if not self.configured:
            return self.stub("pull_orders", {"limit": limit})
        params: dict = {"limit": limit}
        if date_from:
            params["date_from"] = date_from
        if status:
            params["status"] = status

        def _do():
            import requests
            r = requests.get("https://my.prom.ua/api/v1/orders/list",
                headers={"Authorization": f"Bearer {self.creds.get('token')}"},
                params=params, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        return self._call(_do)

    def get_order(self, order_id: str) -> dict:
        def _do():
            import requests
            r = requests.get(f"https://my.prom.ua/api/v1/orders/{order_id}",
                headers={"Authorization": f"Bearer {self.creds.get('token')}"},
                timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        return self._call(_do)

    def set_status(self, order_id: str, status: str) -> dict:
        """Зворотний бік: CRM → Prom (напр. sent/delivered)."""

        def _do():
            import requests
            r = requests.post("https://my.prom.ua/api/v1/orders/set_status",
                headers={"Authorization": f"Bearer {self.creds.get('token')}"},
                json={"id": order_id, "status": status}, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        return self._call(_do)


class RozetkaAdapter(BaseAdapter):
    provider = "rozetka"

    def pull_orders(self, limit: int = 50, date_from: str | None = None) -> dict:
        if not self.configured:
            return self.stub("pull_orders", {"limit": limit})
        # Обмеження API: date_from не задокументовано для пошуку Rozetka,
        # тому приймаємо (щоб sync був одноманітним), але не надсилаємо.
        # Пагінації по offset у відповіді немає — sync зупиниться на seen-наборі.

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


def _items(items: list, name_keys=("name", "title")) -> list:
    """Позиції для upsert_order: [{name, qty, unit_price}]. Цін у фідах може не бути."""
    out = []
    for i in (items or []):
        if not isinstance(i, dict):
            continue
        name = next((str(i.get(k) or "").strip() for k in name_keys if i.get(k)), "")
        if not name:
            continue
        try:
            price = float(i.get("price", 0) or 0)
        except (TypeError, ValueError):
            price = 0
        try:
            qty = float(i.get("quantity", i.get("qty", 1)) or 1)
        except (TypeError, ValueError):
            qty = 1
        out.append({"name": name, "qty": qty, "unit_price": price})
    return out


def normalize_order(provider: str, raw: dict) -> dict:
    """Єдиний формат замовлення -> client + deal."""
    if provider == "prom":
        return {"external_id": str(raw.get("id", "")),
                "name": raw.get("client_first_name", "Клієнт Prom"),
                "phone": raw.get("client_phone", ""),
                "amount": float(raw.get("price", 0) or 0),
                "items": _items(raw.get("products", [])),
                "product_summary": _product_summary(raw.get("products", []))}
    customer = raw.get("customer") if isinstance(raw.get("customer"), dict) else {}
    return {"external_id": str(raw.get("id", "")),
            "name": customer.get("name", "Клієнт Rozetka"),
            "phone": customer.get("phone", ""),
            "amount": float(raw.get("amount", 0) or 0),
            "items": _items(raw.get("items", [])),
            "product_summary": _product_summary(raw.get("items", []))}
