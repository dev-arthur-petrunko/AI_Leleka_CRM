from datetime import datetime, timedelta, timezone

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from jose import jwt

from app.core.config import settings

# passlib[bcrypt]==1.7.4 несумісний з bcrypt>=4.1 (прибрали __about__) —
# на чистому `pip install` це ламає hash_password на БУДЬ-ЯКОМУ паролі
# з незрозумілою помилкою "password cannot be longer than 72 bytes".
# Використовуємо bcrypt напряму, без passlib-прошарку.
_BCRYPT_MAX_BYTES = 72  # обмеження самого алгоритму bcrypt


def hash_password(password: str) -> str:
    raw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    raw = plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.checkpw(raw, hashed.encode("utf-8"))


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
