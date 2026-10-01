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


def create_access_token(sub: str, tenant_id: str, role: str,
                        token_version: int = 0) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": sub, "tenant_id": tenant_id, "role": role,
               "ver": token_version, "type": "access", "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(sub: str, tenant_id: str,
                         token_version: int = 0) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    payload = {"sub": sub, "tenant_id": tenant_id, "ver": token_version,
               "type": "refresh", "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str, expect_type: str | None = None) -> dict:
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if expect_type and payload.get("type", "access") != expect_type:
        from jose import JWTError
        raise JWTError(f"Очікувався токен типу {expect_type}")
    return payload


def verify_signature(secret: str, body: bytes, signature: str | None) -> bool:
    """HMAC-перевірка підпису вебхука (фаза 1.2)."""
    import hashlib
    import hmac

    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


COMMON_PASSWORDS = frozenset(
    "1234567890 12345678 123456789 password password1 password123 qwerty123 "
    "letmein admin123 qwertyuiop 11111111 00000000 iloveyou dragon monkey football "
    "abcdefgh abc123456".split()
)


def check_password_policy(password: str):
    """Мінімум 10 символів + не зі списку частих. Кидає ValueError з причиною."""
    if len(password) < 10:
        raise ValueError("Пароль коротший 10 символів")
    if password.lower() in COMMON_PASSWORDS:
        raise ValueError("Пароль занадто поширений")
    return True


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
