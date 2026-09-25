"""Нова Пошта: автоматичне створення ТТН при оплаті (п.4-5.1 плану)."""

from app.integrations.base import BaseAdapter


class NovaPoshtaAdapter(BaseAdapter):
    provider = "novaposhta"

    def create_ttn(self, recipient_phone: str, recipient_city: str,
                   weight: float = 1.0, cod: float = 0) -> dict:
        if not self.configured:
            return self.stub("create_ttn", {"phone": recipient_phone, "cod": cod})
        api_key = self.creds.get("api_key")

        def _do():
            import requests
            r = requests.post("https://api.novaposhta.ua/v2.0/json/",
                json={"apiKey": api_key, "modelName": "InternetDocument",
                      "calledMethod": "save",
                      "methodProperties": {
                          "NewAddress": "1",
                          "PayerType": "Recipient",
                          "PaymentMethod": "Cash" if not cod else "NonCash",
                          "CargoType": "Parcel",
                          "Weight": str(weight),
                          "ServiceType": "WarehouseWarehouse",
                          "SeatsAmount": "1",
                          "Description": "Замовлення CRM",
                          "Cost": str(cod or 100),
                          "CityRecipient": recipient_city,
                          "RecipientContactName": recipient_phone,
                          "RecipientPhone": recipient_phone}},
                timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        return self._call(_do)
