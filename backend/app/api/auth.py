"""Auth фази 1: компанія в логіні, 2FA, refresh, зміна/скидання пароля, політика."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.core.rate import limiter
from app.core.security import (
    check_password_policy,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models import PasswordResetToken, Tenant, User
from app.schemas import RegisterTenantIn, TokenOut
from app.services.billing import check_seats

router = APIRouter(prefix="/auth", tags=["auth"])

_owner_admin = require_role("owner", "admin")


class InviteIn(BaseModel):
    email: EmailStr
    full_name: str
    role: str = "manager"


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str


class ResetRequestIn(BaseModel):
    email: EmailStr


class ResetConfirmIn(BaseModel):
    token: str
    new_password: str


class TotpSetupOut(BaseModel):
    otpauth_uri: str


class TotpEnableIn(BaseModel):
    code: str


def _tokens(user: User) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(str(user.id), str(user.tenant_id),
                                         user.role, user.token_version),
        refresh_token=create_refresh_token(str(user.id), str(user.tenant_id),
                                           user.token_version),
    )


def _check_totp(user: User, scope: str):
    """2FA для owner/admin з увімкненим TOTP: код передається в scope 'totp:123456'."""
    if not user.totp_secret or user.role not in ("owner", "admin"):
        return
    import pyotp

    code = ""
    for part in (scope or "").split():
        if part.startswith("totp:"):
            code = part[5:]
    try:
        from app.core.security import decrypt_credentials
        secret = decrypt_credentials({"enc": user.totp_secret})["v"]
    except Exception:
        secret = None
    if not secret or not pyotp.TOTP(secret).verify(code, valid_window=1):
        raise HTTPException(401, "Потрібен код 2FA (scope 'totp:123456')")


@router.post("/register", response_model=TokenOut)
@limiter.limit("5/minute")
def register(request: Request, data: RegisterTenantIn,
             db: Session = Depends(get_db)):
    try:
        check_password_policy(data.password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if db.query(Tenant).filter(Tenant.slug == data.slug).first():
        raise HTTPException(400, "slug already taken")
    tenant = Tenant(name=data.tenant_name, slug=data.slug)
    db.add(tenant)
    db.flush()
    user = User(tenant_id=tenant.id, email=data.email,
                password_hash=hash_password(data.password),
                full_name=data.owner_name, role="owner",
                email_confirmed=False)
    db.add(user)
    db.commit()
    return _tokens(user)


@router.post("/login", response_model=TokenOut)
@limiter.limit("10/minute")
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(),
          db: Session = Depends(get_db)):
    """username = email; client_id = slug компанії (фаза 1.4). Без slug — як раніше,
    але при дублях email у різних тенантах вимагаємо компанію (400)."""
    slug = (form.client_id or "").strip() or None
    if slug:
        tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
        if not tenant:
            raise HTTPException(401, "Invalid credentials")
        user = db.query(User).filter(User.tenant_id == tenant.id,
                                     User.email == form.username).first()
    else:
        users = db.query(User).filter(User.email == form.username).all()
        if len(users) > 1:
            raise HTTPException(400, "Email є у кількох компаніях — вкажіть компанію")
        user = users[0] if users else None
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    _check_totp(user, form.scopes and " ".join(form.scopes) or "")
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    out = _tokens(user)
    return out


class RefreshIn(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=TokenOut)
def refresh(data: RefreshIn, db: Session = Depends(get_db)):
    """Обмін refresh-токена (7 днів) на нову пару access+refresh."""
    from uuid import UUID

    from jose import JWTError

    try:
        payload = decode_token(data.refresh_token, expect_type="refresh")
    except JWTError:
        raise HTTPException(401, "Invalid refresh token")
    user = db.query(User).filter(User.id == UUID(payload["sub"])).first()
    if (not user or not user.is_active
            or user.token_version != payload.get("ver", -1)):
        raise HTTPException(401, "Refresh відкликано")
    return _tokens(user)


@router.post("/change-password")
def change_password(data: ChangePasswordIn,
                    user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(401, "Старий пароль невірний")
    try:
        check_password_policy(data.new_password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    user.token_version += 1  # відкликати всі старі токени
    db.commit()
    return {"ok": True}


@router.post("/password-reset-request")
@limiter.limit("5/minute")
def password_reset_request(request: Request, data: ResetRequestIn,
                           db: Session = Depends(get_db)):
    """Завжди 200 (не світимо, чи є email). Посилання — в email або в лог (демо)."""
    raw = secrets.token_urlsafe(24)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    db.add(PasswordResetToken(
        email=data.email, token_hash=digest,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)))
    db.commit()
    _send_reset_email(data.email, raw, db)
    return {"ok": True}


def _send_reset_email(email: str, raw_token: str, db: Session):
    """Через першу активну SMTP-інтеграцію; інакше — у лог (демо-режим)."""
    import logging

    from app.models import Integration

    row = db.query(Integration).filter(
        Integration.provider == "email", Integration.is_active.is_(True)).first()
    if row:
        try:
            from app.core.security import decrypt_credentials
            from app.integrations.email import SmtpEmailAdapter

            creds = decrypt_credentials(row.credentials)
            SmtpEmailAdapter(creds, row.settings).send_email(
                email, "Скидання пароля Leleka",
                f"Токен для скидання (30 хв): {raw_token}")
            return
        except Exception as e:  # noqa: BLE001
            logging.warning("reset email failed: %s", e)
    logging.warning("RESET-TOKEN for %s: %s (демо: нема SMTP)", email, raw_token)


@router.post("/password-reset-confirm")
@limiter.limit("5/minute")
def password_reset_confirm(request: Request, data: ResetConfirmIn,
                           db: Session = Depends(get_db)):
    digest = hashlib.sha256(data.token.encode()).hexdigest()
    row = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == digest, PasswordResetToken.used.is_(False)).first()
    if not row or row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(400, "Токен невалідний або прострочений")
    try:
        check_password_policy(data.new_password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    users = db.query(User).filter(User.email == row.email).all()
    for u in users:
        u.password_hash = hash_password(data.new_password)
        u.token_version += 1
    row.used = True
    db.commit()
    return {"ok": True, "updated": len(users)}


@router.post("/2fa/setup", response_model=TotpSetupOut)
def totp_setup(user: User = Depends(_owner_admin),
               db: Session = Depends(get_db)):
    """Повертає otpauth URI (QR) — відскануйте в аутентифікаторі, потім /2fa/enable."""
    import pyotp

    from app.core.security import encrypt_credentials

    secret = pyotp.random_base32()
    user.totp_secret = encrypt_credentials({"v": secret})["enc"]
    db.commit()
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user.email, issuer_name="AI Leleka CRM")
    return TotpSetupOut(otpauth_uri=uri)


@router.post("/2fa/enable")
def totp_enable(data: TotpEnableIn, user: User = Depends(_owner_admin),
                db: Session = Depends(get_db)):
    import pyotp

    from app.core.security import decrypt_credentials

    try:
        secret = decrypt_credentials({"enc": user.totp_secret})["v"]
    except Exception:
        raise HTTPException(400, "Спочатку /2fa/setup")
    if not pyotp.TOTP(secret).verify(data.code, valid_window=1):
        raise HTTPException(400, "Невірний код")
    return {"ok": True, "message": "2FA увімкнено (вимикається скиданням секрету)"}


@router.post("/invite")
@limiter.limit("10/minute")
def invite(request: Request, data: InviteIn,
           user: User = Depends(_owner_admin),
           db: Session = Depends(get_db)):
    """Запрошення: тимчасовий пароль + must_change_password."""
    if data.role not in ("manager", "viewer"):
        raise HTTPException(400, "role must be manager or viewer")
    check_seats(db, user.tenant_id)
    if db.query(User).filter(User.tenant_id == user.tenant_id,
                             User.email == data.email).first():
        raise HTTPException(400, "Користувач з таким email уже є в компанії")
    temp_password = secrets.token_urlsafe(12)
    new_user = User(tenant_id=user.tenant_id, email=data.email,
                    password_hash=hash_password(temp_password),
                    full_name=data.full_name, role=data.role,
                    must_change_password=True)
    db.add(new_user)
    db.commit()
    return {"ok": True, "email": data.email, "role": data.role,
            "temp_password": temp_password}


class TelegramIn(BaseModel):
    init_data: str


@router.post("/telegram")
def telegram_login(data: TelegramIn, db: Session = Depends(get_db)):
    """Вхід у Mini App в один клік: перевірка HMAC initData + свіжість auth_date."""
    import os
    import time

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        raise HTTPException(501, "Telegram-вхід не налаштовано (TELEGRAM_BOT_TOKEN)")
    try:
        import hashlib
        import hmac as _hmac
        from urllib.parse import parse_qsl

        pairs = dict(parse_qsl(data.init_data, keep_blank_values=True))
        check_hash = pairs.pop("hash", "")
        check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
        secret = hashlib.sha256(bot_token.encode()).digest()
        calc = _hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not _hmac.compare_digest(calc, check_hash):
            raise HTTPException(401, "Bad initData signature")
        if time.time() - int(pairs.get("auth_date", 0)) > 3600:
            raise HTTPException(401, "initData прострочено")
        import json
        tg_user = json.loads(pairs.get("user", "{}"))
        tg_id = str(tg_user.get("id", ""))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Bad initData")
    user = db.query(User).filter(User.telegram_id == tg_id).first() if tg_id else None
    if not user:
        raise HTTPException(404, "Привʼяжіть Telegram у налаштуваннях (POST /auth/telegram/link)")
    return _tokens(user)


@router.post("/telegram/link")
def telegram_link(data: TelegramIn, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """Привʼязка: залогінений користувач підтверджує свій Telegram через initData."""
    import hashlib
    import hmac as _hmac
    import json
    import os
    import time
    from urllib.parse import parse_qsl

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    pairs = dict(parse_qsl(data.init_data, keep_blank_values=True))
    check_hash = pairs.pop("hash", "")
    check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hashlib.sha256(bot_token.encode()).digest()
    calc = _hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not bot_token or not _hmac.compare_digest(calc, check_hash):
        raise HTTPException(401, "Bad initData")
    if time.time() - int(pairs.get("auth_date", 0)) > 3600:
        raise HTTPException(401, "initData прострочено")
    tg_user = json.loads(pairs.get("user", "{}"))
    user.telegram_id = str(tg_user.get("id", ""))
    db.commit()
    return {"ok": True, "telegram_id": user.telegram_id}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "id": str(user.id),
        "tenant_id": str(user.tenant_id),
        "email": user.email,
        "role": user.role,
        "must_change_password": user.must_change_password,
    }
