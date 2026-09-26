from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet, InvalidToken
from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(sub: str, tenant_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": sub, "tenant_id": tenant_id, "role": role, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def _fernet() -> Fernet:
    if not settings.CREDENTIALS_KEY:
        raise RuntimeError(
            "CREDENTIALS_KEY не задано. Згенеруйте: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(settings.CREDENTIALS_KEY.encode())


def encrypt_credentials(plain: dict) -> dict:
    """Шифрує API-ключі перед записом у integrations.credentials."""
    import json

    token = _fernet().encrypt(json.dumps(plain).encode()).decode()
    return {"enc": token}


def decrypt_credentials(stored: dict) -> dict:
    """Розшифровує; старі незашифровані записи повертає як є (для міграції)."""
    import json

    if not stored:
        return {}
    if "enc" not in stored:
        return stored  # legacy-plaintext, буде перешифровано при наступному upsert
    try:
        return json.loads(_fernet().decrypt(stored["enc"].encode()).decode())
    except InvalidToken as e:
        raise RuntimeError("Не вдалося розшифрувати credentials: невірний CREDENTIALS_KEY") from e
