"""Checkbox РРО/ПРРО: обов'язкова фіскалізація (п.4 плану)."""

from app.integrations.base import BaseAdapter


class CheckboxAdapter(BaseAdapter):
    provider = "checkbox"

    def fiscal_receipt(self, amount: float, goods: list[dict] | None = None) -> dict:
        if not self.configured:
            return self.stub("fiscal_receipt", {"amount": amount})
        login, password = self.creds.get("login"), self.creds.get("password")

        def _do():
            import requests
            # 1. signin
            s = requests.post("https://api.checkbox.ua/api/v1/cashier/signin",
                json={"login": login, "password": password},
                timeout=self.timeout)
            s.raise_for_status()
            token = s.json().get("access_token")
            # 2. чек
            r = requests.post("https://api.checkbox.ua/api/v1/receipts/sell",
                headers={"Authorization": f"Bearer {token}"},
                json={"goods": goods or [{"good": {"code": "1", "name": "Товар"},
                                          "sum": int(amount * 100)}],
                      "payments": [{"type": "CASH", "value": int(amount * 100)}]},
                timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        return self._call(_do)
