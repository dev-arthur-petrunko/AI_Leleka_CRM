import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


# ---------- Auth ----------
class RegisterTenantIn(BaseModel):
    tenant_name: str
    slug: str
    owner_name: str
    email: EmailStr
    password: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Clients ----------
class ClientIn(BaseModel):
    name: str
    phone: str | None = None
    email: str | None = None
    source: str = "manual"
    notes: str = ""
    assigned_to: uuid.UUID | None = None


class ClientOut(ClientIn):
    id: uuid.UUID
    tenant_id: uuid.UUID
    segment: str
    created_at: datetime


# ---------- Deals ----------
class DealIn(BaseModel):
    client_id: uuid.UUID
    title: str
    amount: float = 0
    stage: str = "new"
    manager_id: uuid.UUID | None = None


class DealOut(DealIn):
    id: uuid.UUID
    tenant_id: uuid.UUID


# ---------- Tasks ----------
class TaskIn(BaseModel):
    title: str
    assignee_id: uuid.UUID | None = None
    client_id: uuid.UUID | None = None
    deal_id: uuid.UUID | None = None
    due_at: datetime | None = None


class TaskOut(TaskIn):
    id: uuid.UUID
    status: str
