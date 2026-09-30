# -*- coding: utf-8 -*-
"""Тестова інфраструктура (фаза 0.2): окрема БД, фабрики, клієнт.

БД створюється один раз (порожня); схема — міграціями:
  TEST_DATABASE_URL=... alembic upgrade head && pytest -q
Локально проти docker-стека: TEST_DATABASE_URL=postgresql+psycopg2://leleka:leleka@localhost:5432/leleka_test
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://leleka:leleka@localhost:5432/leleka_test",
)


def _ensure_db():
    from sqlalchemy.engine import make_url

    url = make_url(TEST_DB_URL)
    server_url = url._replace(database="postgres")
    eng = create_engine(server_url)
    with eng.connect() as c:
        c = c.execution_options(isolation_level="AUTOCOMMIT")
        exists = c.execute(
            text("SELECT 1 FROM pg_database WHERE datname=:d"), {"d": url.database}
        ).first()
        if not exists:
            c.execute(text(f'CREATE DATABASE "{url.database}"'))
    eng.dispose()


_ensure_db()

from app.core.security import create_access_token  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.models import Tenant, User  # noqa: E402

engine = create_engine(TEST_DB_URL)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture()
def db():
    s = TestingSession()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture()
def client(db):
    from app.main import app

    def _override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def make_tenant(db, slug=None, plan="free"):
    slug = slug or f"t-{uuid.uuid4().hex[:8]}"
    t = Tenant(name=slug, slug=slug, plan=plan)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def make_user(db, tenant, role="manager", email=None):
    from app.core.security import hash_password

    email = email or f"u-{uuid.uuid4().hex[:8]}@t.ua"
    u = User(tenant_id=tenant.id, email=email,
             password_hash=hash_password("Test123456"), full_name="Test",
             role=role)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def auth_headers(user):
    tok = create_access_token(str(user.id), str(user.tenant_id), user.role)
    return {"Authorization": f"Bearer {tok}"}
