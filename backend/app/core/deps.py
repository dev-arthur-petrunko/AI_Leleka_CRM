"""tenant_id из JWT — сердце мультитенантности.

Категорично: каждый запрос к бизнес-таблицам обязан фильтровать
по tenant_id из токена, а не из query/body (иначе утечка между компаниями).
"""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        tenant_id: str = payload.get("tenant_id")
        if not user_id or not tenant_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    user = (
        db.query(User)
        .filter(User.id == UUID(user_id), User.tenant_id == UUID(tenant_id))
        .first()
    )
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def get_current_tenant(current_user: User = Depends(get_current_user)) -> UUID:
    """Использовать во всех CRUD: .filter(Model.tenant_id == tenant_id)."""
    return current_user.tenant_id


def require_role(*allowed: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="Forbidden: role not allowed")
        return user

    return checker


def require_plan_feature(feature: str):
    """Блокує платні фічі для тарифів без них (402). Вішається на роутер цілком."""

    def checker(
        user: User = Depends(get_current_user), db: Session = Depends(get_db)
    ) -> User:
        from app.models import Tenant
        from app.services.billing import current_plan

        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
        if feature not in current_plan(tenant)["features"]:
            raise HTTPException(
                status_code=402,
                detail=f"Фіча '{feature}' недоступна на тарифі '{tenant.plan}'. "
                "POST /billing/upgrade",
            )
        return user

    return checker
