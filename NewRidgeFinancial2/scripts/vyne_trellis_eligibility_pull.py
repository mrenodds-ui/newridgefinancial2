"""Headed Playwright: login Vyne Trellis and scrape Appointments Eligibility table.

Credentials from env or .env.vyne.local. Output under app_data/nr2/vyne_pulls (local).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "app_data" / "nr2" / "vyne_pulls"
ENV_FILE = ROOT / ".env.vyne.local"


def _load_env() -> None:
    if not ENV_FILE.is_file():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def main() -> int:
    _load_env()
    user = os.environ.get("VYNE_AUTOMATION_USERNAME", "").strip()
    password = os.environ.get("VYNE_AUTOMATION_PASSWORD", "").strip()
    url = os.environ.get("VYNE_TRELLIS_URL", "https://app.vynetrellis.com").strip()
    if not user or not password:
        print("Missing VYNE_AUTOMATION_USERNAME / PASSWORD", file=sys.stderr)
        return 2

    from playwright.sync_api import sync_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    result: dict = {
        "ok": False,
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "url": url,
        "rows": [],
        "error": "",
        "finalUrl": "",
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(1500)
            # Auth page
            if "authenticate" in page.url or page.get_by_label("Email").count():
                page.get_by_label("Email").fill(user)
                page.get_by_label("Password").fill(password)
                page.get_by_role("button", name="Continue").click()
                page.wait_for_timeout(2500)

            # Org select
            if page.get_by_text("Select an organization").count():
                org = page.get_by_text("Michael Christian Reno DDS PA").first
                org.click()
                page.wait_for_timeout(4000)

            # Wait for app
            for _ in range(30):
                if "app.vynetrellis.com" in page.url and "authenticate" not in page.url:
                    break
                if page.get_by_text("Unable to sign in").count():
                    raise RuntimeError("Unable to sign in after org select")
                page.wait_for_timeout(1000)
            result["finalUrl"] = page.url
            page.screenshot(path=str(OUT_DIR / f"vyne_home_{stamp}.png"), full_page=True)

            # Navigate eligibility / appointments
            for label in ("Appointments", "Eligibility", "Insurance", "Patients"):
                loc = page.get_by_role("link", name=re.compile(label, re.I))
                if loc.count():
                    loc.first.click()
                    page.wait_for_timeout(2000)
                    break
                btn = page.get_by_role("button", name=re.compile(label, re.I))
                if btn.count():
                    btn.first.click()
                    page.wait_for_timeout(2000)
                    break
                text = page.get_by_text(re.compile(rf"^{label}$", re.I))
                if text.count():
                    text.first.click()
                    page.wait_for_timeout(2000)

            # Try direct paths
            for path in (
                "/appointments",
                "/eligibility",
                "/Appointments/Eligibility",
                "/insurance/eligibility",
            ):
                try:
                    page.goto("https://app.vynetrellis.com" + path, wait_until="domcontentloaded", timeout=20000)
                    page.wait_for_timeout(1500)
                    if "authenticate" not in page.url:
                        break
                except Exception:
                    continue

            result["finalUrl"] = page.url
            page.screenshot(path=str(OUT_DIR / f"vyne_elig_{stamp}.png"), full_page=True)

            # Scrape visible tables
            tables = page.locator("table")
            n = tables.count()
            for i in range(min(n, 5)):
                rows = tables.nth(i).locator("tr")
                for r in range(rows.count()):
                    cells = rows.nth(r).locator("th,td")
                    vals = [cells.nth(c).inner_text().strip() for c in range(cells.count())]
                    if any(vals):
                        result["rows"].append(vals)

            # Also collect list-like eligibility cards
            body = page.inner_text("body")
            result["bodyPreview"] = body[:4000]
            result["ok"] = "authenticate" not in page.url
            if not result["ok"]:
                result["error"] = "still on authenticate"
        except Exception as exc:  # noqa: BLE001
            result["error"] = str(exc)
            try:
                page.screenshot(path=str(OUT_DIR / f"vyne_error_{stamp}.png"), full_page=True)
            except Exception:
                pass
        finally:
            context.close()
            browser.close()

    out = OUT_DIR / f"vyne_eligibility_pull_{stamp}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"ok": result["ok"], "error": result.get("error"), "rows": len(result.get("rows") or []), "path": str(out), "finalUrl": result.get("finalUrl")}, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
