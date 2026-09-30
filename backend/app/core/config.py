from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://leleka:leleka@localhost:5432/leleka_crm"
    # БЕЗ дефолта: без SECRET_KEY додаток не стартує (старе значення скомпрометоване — див. README).
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h для MVP

    # Fernet-ключ для шифрування credentials в integrations.credentials
    # Згенерувати: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    CREDENTIALS_KEY: str = ""

    REDIS_URL: str = "redis://localhost:6379/0"
    # Домени фронту через кому: WebApp, localhost, прод-домен.
    # :8080 — локальне превʼю (python -m http.server у frontend-preview/):
    # file:// має origin null і ріжеться браузером, тому превʼю відкриваємо по http.
    FRONTEND_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:8080,http://127.0.0.1:8080,https://web.telegram.org"

    # Ключі ПЛАТФОРМИ (власника сервісу) для прийому оплати тарифів.
    # Без них платний апгрейд повертає 409 (діра «безкоштовний Team» закрита).
    PLATFORM_LIQPAY_PUBLIC_KEY: str = ""
    PLATFORM_LIQPAY_PRIVATE_KEY: str = ""
    PLATFORM_MONO_TOKEN: str = ""

    # AI-шаблони листів клієнтам (services/messaging.py). Без ключа —
    # чесний локальний шаблон, MVP не падає. Модель — перевірте
    # актуальну назву на docs.claude.com, вони змінюються з часом.
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-5"

    class Config:
        env_file = ".env"


settings = Settings()

if not settings.SECRET_KEY or len(settings.SECRET_KEY) < 32:
    raise RuntimeError(
        "SECRET_KEY не задано або коротше 32 символів. "
        "Згенеруйте: openssl rand -hex 32 — і покладіть у .env (див. .env.example). "
        "Старе дефолтне значення з репозиторію вважається скомпрометованим."
    )


def frontend_origins() -> list[str]:
    return [o.strip() for o in settings.FRONTEND_ORIGINS.split(",") if o.strip()]
