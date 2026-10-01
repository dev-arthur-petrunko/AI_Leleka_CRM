# -*- coding: utf-8 -*-
"""Безпека фази 1: вебхуки, логін з компанією, паролі, 2FA, відкликання."""

import hashlib
import hmac
import json
import uuid

from tests.conftest import auth_headers, make_tenant, make_user


def test_pending_requires_owner(client, db):
    from app.models import User

    t = make_tenant(db)
    mgr = make_user(db, t, role="manager")
    assert client.get("/webhooks/pending").status_code == 401
    assert client.get("/webhooks/pending",
                      headers=auth_headers(mgr)).status_code == 403
    owner = make_user(db, t, role="owner")
    assert client.get("/webhooks/pending",
                      headers=auth_headers(owner)).status_code == 200


def test_signed_webhook_flow(client, db):
    from app.core.security import decrypt_credentials, encrypt_credentials
    from app.models import Integration

    t = make_tenant(db)
    owner = make_user(db, t, role="owner")
    secret = "s3cr3t-32-bytes-long-value-xxxx"
    row = Integration(tenant_id=t.id, provider="prom", credentials={},
                      webhook_secret=encrypt_credentials({"v": secret})["enc"])
    db.add(row)
    db.commit()
    url = f"/webhooks/prom/{row.id}"
    body = json.dumps({"id": "1001"}).encode()
    assert client.post(url, content=body).status_code in (401, 404)
    assert client.post(url + "?secret=wrong", content=body).status_code == 401
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    r = client.post(url, content=body, headers={"X-Signature": sig})
    assert r.status_code == 200, r.text
    # повтор — дедуплікація в межах тенанта
    r2 = client.post(url, content=body, headers={"X-Signature": sig})
    assert r2.json().get("deduplicated") is True


def test_login_company_scope(client, db):
    ta = make_tenant(db, slug=f"ca-{uuid.uuid4().hex[:6]}")
    tb = make_tenant(db, slug=f"cb-{uuid.uuid4().hex[:6]}")
    make_user(db, ta, email="same@t.ua")
    make_user(db, tb, email="same@t.ua")
    # без компанії — вимагаємо slug
    r = client.post("/auth/login", data={"username": "same@t.ua", "password": "Test123456"})
    assert r.status_code == 400
    # з slug — кожен у свій тенант
    for tenant in (ta, tb):
        r = client.post("/auth/login", data={"username": "same@t.ua",
                                             "password": "Test123456",
                                             "client_id": tenant.slug})
        assert r.status_code == 200, r.text


def test_password_policy_and_change(client, db):
    t = make_tenant(db)
    u = make_user(db, t, role="owner")
    h = auth_headers(u)
    # короткий і поширений — 400
    assert client.post("/auth/change-password", headers=h,
                       json={"old_password": "Test123456",
                             "new_password": "short"}).status_code == 400
    assert client.post("/auth/change-password", headers=h,
                       json={"old_password": "Test123456",
                             "new_password": "password123"}).status_code == 400
    # старий токен після зміни — відкликано
    assert client.post("/auth/change-password", headers=h,
                       json={"old_password": "Test123456",
                             "new_password": "N0vyi-Dovhyi-99"}).status_code == 200
    assert client.get("/auth/me", headers=h).status_code == 401


def test_refresh_flow(client, db):
    t = make_tenant(db)
    u = make_user(db, t, role="owner")
    r = client.post("/auth/login",
                    data={"username": u.email, "password": "Test123456"})
    rt = r.json()["refresh_token"]
    r2 = client.post("/auth/refresh", json={"refresh_token": rt})
    assert r2.status_code == 200
    assert client.post("/auth/refresh",
                       json={"refresh_token": "bad"}).status_code == 401


def test_totp_flow(client, db):
    t = make_tenant(db)
    u = make_user(db, t, role="owner")
    h = auth_headers(u)
    uri = client.post("/auth/2fa/setup", headers=h).json()["otpauth_uri"]
    assert uri.startswith("otpauth://")
    import pyotp

    secret = uri.split("secret=")[1].split("&")[0]
    code = pyotp.TOTP(secret).now()
    assert client.post("/auth/2fa/enable", headers=h,
                       json={"code": code}).status_code == 200
    # без коду — 401, з кодом — 200
    assert client.post("/auth/login", data={"username": u.email,
                                            "password": "Test123456"}).status_code == 401
    code = pyotp.TOTP(secret).now()
    r = client.post("/auth/login", data={"username": u.email, "password": "Test123456",
                                         "scope": f"totp:{code}"})
    assert r.status_code == 200


def test_must_change_password_enforced(client, db):
    import uuid as _uuid

    tag = _uuid.uuid4().hex[:6]
    email = f"new-{tag}@t.ua"
    t = make_tenant(db, slug=f"mcp-{tag}", plan="pro")
    owner = make_user(db, t, role="owner", email=f"o-{tag}@t.ua")
    ho = auth_headers(owner)
    r = client.post("/auth/invite", headers=ho,
                    json={"email": email, "full_name": "New", "role": "manager"})
    temp_pw = r.json()["temp_password"]
    rl = client.post("/auth/login",
                     data={"username": email, "password": temp_pw}).json()
    hn = {"Authorization": f"Bearer {rl['access_token']}"}
    assert client.get("/clients", headers=hn).status_code == 403
    assert client.get("/auth/me", headers=hn).status_code == 200
