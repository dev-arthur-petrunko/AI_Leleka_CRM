"""Playwright-снимки основных экранов: 390/1280 px x Ранок/Вечір + проверка прокрутки.

Использование (локально, из корня репо):
  1. docker compose up -d db redis api
  2. cd frontend && npm run dev  (5173, VITE_API_BASE=http://localhost:8000)
  3. python scripts/snapshots.py --base http://localhost:5173 --api http://localhost:8000

Выход: frontend/snapshots/*.png (в .gitignore). Падает при горизонтальной
прокрутке или HTTP-ошибке страницы.
"""

import argparse
import sys
import uuid

import requests
from playwright.sync_api import sync_playwright

ROUTES = ["/", "/deals", "/orders", "/clients", "/analytics", "/settings"]
VIEWPORTS = [(390, 844), (1280, 800)]
THEMES = ["morning", "evening"]


def register(api: str) -> tuple[str, str]:
    tag = uuid.uuid4().hex[:8]
    r = requests.post(
        f"{api}/auth/register",
        json={"tenant_name": f"Shot {tag}", "slug": f"shot-{tag}",
              "owner_name": "Shot", "email": f"shot-{tag}@t.ua",
              "password": "Longpassword123"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"], tag


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:5173")
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--out", default="snapshots")
    ap.add_argument("--serve", default="",
                    help="поднять vite preview из dist/: --serve 4173")
    ap.add_argument("--reduced", action="store_true",
                    help="prefers-reduced-motion + анімації off: нічого не має рухатись")
    args = ap.parse_args()

    import pathlib
    import subprocess
    import time
    import urllib.request

    srv = None
    if args.serve:
        root = pathlib.Path(__file__).parent.parent
        srv = subprocess.Popen(
            ["cmd", "/c", "npx", "vite", "preview", "--port", args.serve, "--strictPort"],
            cwd=str(root), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        base = f"http://localhost:{args.serve}"
        for _ in range(60):
            try:
                urllib.request.urlopen(base, timeout=2)
                break
            except Exception:
                time.sleep(1)
        else:
            print("preview not up")
            srv.terminate()
            return 2
        args.base = base
    try:
        return run(args)
    finally:
        if srv:
            srv.terminate()


def run(args) -> int:
    import pathlib
    out = pathlib.Path(__file__).parent.parent / args.out
    if args.reduced:
        out = out / "reduced"
    out.mkdir(exist_ok=True, parents=True)

    token, tag = register(args.api)
    print("registered", tag)
    fails: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for w, h in VIEWPORTS:
            for theme in THEMES:
                ctx = browser.new_context(
                    viewport={"width": w, "height": h},
                    reduced_motion="reduce" if args.reduced else "no-preference",
                )
                ctx.add_init_script(
                    f"localStorage.setItem('leleka-token','{token}');"
                    f"localStorage.setItem('leleka.themeMode','{theme}');"
                    + ("localStorage.setItem('leleka.animations','off');"
                       "localStorage.setItem('leleka.celebration','compact');"
                       if args.reduced else "")
                )
                page = ctx.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                for route in ROUTES:
                    name = f"{w}x{theme}{route.replace('/', '_') or '_root'}.png"
                    page.goto(args.base + route, wait_until="networkidle")
                    page.wait_for_timeout(800)
                    overflow = page.evaluate(
                        "document.scrollingElement.scrollWidth - window.innerWidth")
                    if overflow > 1:
                        fails.append(f"{name}: horizontal overflow {overflow}px")
                    if errors:
                        fails.append(f"{name}: js errors {errors[:2]}")
                        errors.clear()
                    page.screenshot(path=str(out / name))
                    print("shot", name)
                ctx.close()
        browser.close()
    if fails:
        print("FAILURES:")
        for f in fails:
            print(" -", f)
        return 1
    print("all snapshots ok:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
