import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.core.rate import limiter
from app.models import Tenant, User
from app.schemas import LoginIn, RegisterTenantIn, TokenOut
from app.services.billing import check_seats

router = APIRouter(prefix="/auth", tags=["auth"])

_owner_admin = require_role("owner", "admin")


class InviteIn(BaseModel):
    email: EmailStr
    full_name: str
    role: str = "manager"  # manager/viewer (owner створюється тільки через /register)


@router.post("/register", response_model=TokenOut)
def register(data: RegisterTenantIn, db: Session = Depends(get_db)):
    if db.query(Tenant).filter(Tenant.slug == data.slug).first():
        raise HTTPException(400, "slug already taken")
    tenant = Tenant(name=data.tenant_name, slug=data.slug)
    db.add(tenant)
    db.flush()  # получить tenant.id
    user = User(
        tenant_id=tenant.id,
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.owner_name,
        role="owner",
    )
    db.add(user)
    db.commit()
    token = create_access_token(str(user.id), str(tenant.id), user.role)
    return TokenOut(access_token=token)


@router.post("/login", response_model=TokenOut)
@limiter.limit("10/minute")
def login(request: Request, data: LoginIn, db: Session = Depends(get_db)):
    """Брутфорс-захист: 10 спроб/хв з IP."""
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    from datetime import datetime, timezone
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    token = create_access_token(str(user.id), str(user.tenant_id), user.role)
    return TokenOut(access_token=token)


@router.post("/invite")
def invite(data: InviteIn, user: User = Depends(_owner_admin),
           db: Session = Depends(get_db)):
    """Запрошення співробітника в тенант (закриває розрив: місця тарифу реально використовуються)."""
    if data.role not in ("manager", "viewer"):
        raise HTTPException(400, "role must be manager or viewer")
    check_seats(db, user.tenant_id)  # 402 якщо місця вичерпано
    if db.query(User).filter(User.tenant_id == user.tenant_id,
                             User.email == data.email).first():
        raise HTTPException(400, "Користувач з таким email уже є в компанії")
    temp_password = secrets.token_urlsafe(10)
    new_user = User(tenant_id=user.tenant_id, email=data.email,
                    password_hash=hash_password(temp_password),
                    full_name=data.full_name, role=data.role)
    db.add(new_user)
    db.commit()
    # Тимчасовий пароль повертається ОДИН раз — передайте його співробітнику окремим каналом
    return {"ok": True, "email": data.email, "role": data.role,
            "temp_password": temp_password}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "id": str(user.id),
        "tenant_id": str(user.tenant_id),
        "email": user.email,
        "role": user.role,
    }
