"""Мультиканальні листи клієнтам (Telegram/Viber/Email) з AI-текстом.

Дизайн навмисно узгоджений з GDPR-принципом, який вже діє в проєкті
(services/ai.py: "PII (phone/email/name) НІКОЛИ не йде в зовнішній AI").
Тому зовнішньому AI віддається ТІЛЬКИ назва товару (це не персональні
дані — це опис товару), і він повертає ШАБЛОН із плейсхолдерами
{greeting}/{product_line}/{order_line}. Ім'я клієнта та номер
замовлення підставляються ЛОКАЛЬНО, вже після відповіді AI, і ніколи
не покидають ваш сервер.

Якщо потрібен простіший варіант — AI одразу пише повністю готовий
персоналізований текст (менше коду, але ім'я й номер замовлення підуть
у зовнішній Anthropic/OpenAI API) — це свідомо НЕ дефолт тут; якщо
хочете саме так, змініть generate_template() на прямий виклик з
повними даними клієнта в промпті.
"""

from app.core.config import settings
from app.models import Client, Deal

_FALLBACK_TEMPLATES = {
    "email": ("{greeting}\n\n"
              "Дякуємо за замовлення{product_line}{order_line}!\n"
              "Якщо виникнуть питання — просто дайте знати, ми завжди на звʼязку.\n\n"
              "З теплом,\nваша команда"),
    "telegram": "{greeting} Дякуємо за замовлення{product_line}{order_line}! 🙌 "
               "Якщо будуть питання — пишіть сюди.",
    "viber": "{greeting} Дякуємо за замовлення{product_line}{order_line}! "
            "Ми на звʼязку, якщо що.",
}

SUPPORTED_CHANNELS = ("email", "telegram", "viber")


def _greeting(first_name: str | None, last_name: str | None) -> str:
    """Коректне звернення для БУДЬ-ЯКОЇ комбінації відомих полів —
    саме та "логіка врахування відсутніх даних", яку і має ця фіча."""
    full = " ".join(p for p in (first_name, last_name) if p)
    return f"Доброго дня, {full}!" if full else "Доброго дня!"


def _product_line(product_summary: str | None) -> str:
    return f" ({product_summary})" if product_summary else ""


def _order_line(order_number: str | None) -> str:
    return f", номер {order_number}" if order_number else ""


def _safe_format(template: str, **kwargs) -> str | None:
    """AI могла повернути текст із чужим {щось} — тоді .format() впаде
    з KeyError. Ловимо це і відкочуємось на локальний шаблон, а не 500."""
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return None


def generate_template(product_summary: str | None, channel: str) -> dict:
    """AI бачить ТІЛЬКИ назву товару (не PII). Без ключа — локальний фолбек."""
    if not settings.ANTHROPIC_API_KEY:
        return {"template": _FALLBACK_TEMPLATES[channel], "ai_used": False}

    subject = f"товару: {product_summary}" if product_summary else "(товар невідомий — пиши загально)"
    prompt = (
        f"Напиши короткий дружній шаблон подяки клієнту за покупку {subject} "
        f"для каналу {channel}. Мова — українська, тон теплий, без канцеляризмів. "
        "У тексті використай РІВНО ПО ОДНОМУ РАЗУ плейсхолдери {greeting}, "
        "{product_line} та {order_line} буквально в фігурних дужках — це "
        "єдині фігурні дужки, які можна використовувати в тексті. "
        "Нічого персонального (імен, номерів) сам не вигадуй."
    )
    try:
        import requests
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": settings.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"},
            json={"model": settings.ANTHROPIC_MODEL, "max_tokens": 300,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=15)
        r.raise_for_status()
        text = r.json()["content"][0]["text"].strip()
        return {"template": text, "ai_used": True}
    except Exception as e:
        return {"template": _FALLBACK_TEMPLATES[channel], "ai_used": False, "ai_error": str(e)}


def compose_message(client: Client, deal: Deal | None, channel: str) -> dict:
    """Готовий текст + прапорці, яких саме даних не вистачало (для UI/логів)."""
    if channel not in SUPPORTED_CHANNELS:
        raise ValueError(f"Невідомий канал: {channel}. Підтримуються: {SUPPORTED_CHANNELS}")

    product_summary = deal.product_summary if deal else None
    order_number = deal.order_number if deal else None

    tpl = generate_template(product_summary, channel)
    fmt_kwargs = {"greeting": _greeting(client.first_name, client.last_name),
                  "product_line": _product_line(product_summary),
                  "order_line": _order_line(order_number)}
    text = _safe_format(tpl["template"], **fmt_kwargs)
    if text is None:  # AI повернула зіпсований шаблон — відкат на гарантовано робочий
        text = _FALLBACK_TEMPLATES[channel].format(**fmt_kwargs)
        tpl["ai_used"] = False
        tpl["ai_template_rejected"] = True

    return {"text": text, "ai_used": tpl["ai_used"],
            "ai_template_rejected": tpl.get("ai_template_rejected", False),
            "missing": {"first_name": not client.first_name,
                        "last_name": not client.last_name,
                        "order_number": not order_number,
                        "product": not product_summary}}
