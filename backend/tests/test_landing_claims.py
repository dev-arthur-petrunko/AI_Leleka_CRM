"""Лендинг не бреше про тарифи: ціни/місця в about.html == PLANS у billing.py.

Увага: в api-контейнері фронта нема (монтується лише ./backend),
тому без about.html — skip (у CI репо повне, тест працює).
"""

import pathlib
import re

import pytest


def _root():
    base = pathlib.Path(__file__).resolve()
    for c in [base.parent.parent.parent, base.parent.parent, base.parent]:
        if (c / "frontend" / "public" / "about.html").exists():
            return c
    return None


def _landing():
    root = _root()
    if root is None:
        pytest.skip("нема frontend/ у цьому оточенні (окремо змонтований backend)")
    return (root / "frontend" / "public" / "about.html").read_text(encoding="utf-8")


def test_landing_prices_match_plans():
    from app.services.billing import PLANS

    t = _landing()
    assert "350" in t and "300" in t, "ціни Pro/Team мають бути на лендингу"
    assert PLANS["pro"]["price_uah"] == 350
    assert PLANS["team"]["price_uah"] == 300
    assert PLANS["free"]["price_uah"] == 0
    # місця: Pro «до 5» == ліміт 5; Team «5+» — ліміт не менше 5
    assert PLANS["pro"]["seats"] == 5
    assert PLANS["team"]["seats"] >= 5
    # при 5 місцях Team справді дешевше за Pro (як написано на лендингу)
    assert 5 * PLANS["team"]["price_uah"] < 5 * PLANS["pro"]["price_uah"]


def test_landing_no_dead_links():
    t = _landing()
    assert "localhost" not in t, "localhost на прод-лендингу"
    assert "login.html" not in t, "login.html не шипиться в public/"
    assert "dashboard.html" not in t, "dashboard.html не шипиться в public/"
    assert "зіллють" not in t, "неперевіряна фраза"
    for img in re.findall(r'src="(assets/[^"]+)"', t):
        root = _root()
        assert root is not None
        p = root / "frontend" / "public" / img
        assert p.exists(), f"картинки нема: {img}"
