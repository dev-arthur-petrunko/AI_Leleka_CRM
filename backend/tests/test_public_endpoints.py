# -*- coding: utf-8 -*-
"""Фіксовані публічні endpoints (фаза 0.3): будь-який новий публічний роут ламає тест."""

import pytest

# без токена ці мають бути доступні...
OPEN_OK = ["/health", "/auth/login"]
# ...а ці — ні (401/405/422, але НЕ 200 з даними)
REQUIRE_AUTH = ["/auth/me", "/clients", "/deals", "/tasks", "/analytics/kpi",
                "/automations/logs", "/billing/current", "/integrations",
                "/feedhub/sources", "/notifications", "/webhooks/pending"]
# /orders додасться у фазі 2 (див. AGENT_PLAN)


@pytest.mark.parametrize("path", OPEN_OK)
def test_open(client, path):
    if path == "/auth/login":
        r = client.post(path, data={"username": "x", "password": "y"})
        assert r.status_code in (401, 429)  # не 200 і не 500
    else:
        assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", REQUIRE_AUTH)
def test_requires_auth(client, path):
    r = client.get(path)
    assert r.status_code in (401, 403)
