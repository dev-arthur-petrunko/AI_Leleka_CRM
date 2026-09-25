from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://leleka:leleka@localhost:5432/leleka_crm"
    SECRET_KEY: str = "change-me-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h для MVP

    # Fernet-ключ для шифрования credentials в integrations.credentials
    # Сгенерировать: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    CREDENTIALS_KEY: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
