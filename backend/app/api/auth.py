from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_tenant, get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models import Tenant, User
from app.schemas import LoginIn, RegisterTenantIn, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])


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
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    token = create_access_token(str(user.id), str(user.tenant_id), user.role)
    return TokenOut(access_token=token)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "id": str(user.id),
        "tenant_id": str(user.tenant_id),
        "email": user.email,
        "role": user.role,
    }
