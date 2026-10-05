"""Caddyfile покриває всі шляхи API (і ховає docs): регресія проти main.app."""

import pathlib
import re


def _caddy():
    p = pathlib.Path(__file__).resolve()
    for c in [p.parent.parent.parent, p.parent.parent, p.parent]:
        if (c / "Caddyfile").exists():
            return (c / "Caddyfile").read_text(encoding="utf-8")
    import pytest

    pytest.skip("нема Caddyfile в цьому оточенні")


def _api_tokens():
    t = _caddy()
    m = re.search(r"@api path (.+)", t)
    assert m, "@api path не знайдено в Caddyfile"
    return m.group(1).split()


def _covered(path: str, tokens: list) -> bool:
    for tok in tokens:
        if tok.endswith("*"):
            if path == tok[:-1] or path.startswith(tok[:-1] + "/") or path.startswith(tok[:-1]):
                return True
        elif path == tok:
            return True
    return False


def test_caddy_covers_backend_routes():
    from fastapi.routing import APIRoute

    from app.main import app

    tokens = _api_tokens()
    missing = []
    for r in app.routes:
        if not isinstance(r, APIRoute):
            continue
        path = r.path
        if path in ("/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"):
            continue  # docs свідомо не проксуємо в проді
        if not _covered(path, tokens):
            missing.append(path)
    assert not missing, f"Caddy не проксує: {sorted(set(missing))}"


def test_caddy_hides_docs():
    t = _caddy()
    api_line = re.search(r"@api path (.+)", t).group(1)
    for hidden in ("/docs", "/openapi.json", "/redoc"):
        assert hidden not in api_line.split(), f"{hidden} світиться в проді"
    assert "text/html" in t, "нема Accept-розділення SPA/API"
