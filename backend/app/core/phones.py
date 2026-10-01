"""Нормалізація телефонів (фаза 2.2): +380…, 380…, 0… → один формат +E.164."""

import re


def normalize_phone(raw: str | None, default_cc: str = "380") -> str | None:
    if not raw:
        return None
    d = re.sub(r"\D", "", raw)
    d = d.removeprefix("00")
    if len(d) == 10 and d.startswith("0"):  # 0501234567
        d = default_cc + d[1:]
    elif len(d) == 9:  # 501234567
        d = default_cc + d
    if not 11 <= len(d) <= 15:
        return None
    return "+" + d
