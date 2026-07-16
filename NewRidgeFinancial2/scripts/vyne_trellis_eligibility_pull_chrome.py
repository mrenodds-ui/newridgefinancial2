"""Trellis pull using system Chrome channel — often works better with Stytch."""

from __future__ import annotations

import json
import os
import sys
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
    user = os.environ["VYNE_AUTOMATION_USERNAME"].strip()
    password = os.environ["VYNE_AUTOMATION_PASSWORD"].strip()
    from playwright.sync_api import sync_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    result = {"ok": False, "error": "", "finalUrl": "", "bodyPreview": "", "rows": []}

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=False)
        except Exception:
            browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1440, "height": 960})
        page = context.new_page()
        try:
            page.goto(
                "https://auth.vynetrellis.com/authenticate?redirect_uri=https%3A%2F%2Fapp.vynetrellis.com&productType=Trellis",
                wait_until="domcontentloaded",
                timeout=90000,
            )
            page.get_by_label("Email").fill(user)
            page.get_by_label("Password").fill(password)
            page.get_by_role("button", name="Continue").click()
            page.wait_for_timeout(4000)
            page.locator("li").filter(has_text="Michael Christian Reno").first.click()
            # Wait for real app content (not blank)
            page.wait_for_timeout(10000)
            for _ in range(30):
                url = page.url
                text = page.locator("body").inner_text()
                if "authenticate" not in url and len(text.strip()) > 80 and "Log in" not in text[:40]:
                    break
                page.wait_for_timeout(1000)
            result["finalUrl"] = page.url
            result["bodyPreview"] = page.locator("body").inner_text()[:10000]
            page.screenshot(path=str(OUT_DIR / f"vyne_chrome_{stamp}.png"), full_page=True)

            # Go appointments
            page.goto("https://app.vynetrellis.com/appointments", wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(8000)
            page.screenshot(path=str(OUT_DIR / f"vyne_chrome_appts_{stamp}.png"), full_page=True)
            result["bodyPreview"] = page.locator("body").inner_text()[:12000]
            result["finalUrl"] = page.url
            result["ok"] = "authenticate" not in page.url and len(result["bodyPreview"].strip()) > 40

            # Try eligibility text
            if page.get_by_text("Eligibility").count():
                page.get_by_text("Eligibility").first.click()
                page.wait_for_timeout(5000)
                page.screenshot(path=str(OUT_DIR / f"vyne_chrome_elig_{stamp}.png"), full_page=True)
                result["bodyPreview"] = page.locator("body").inner_text()[:12000]

            for i in range(min(page.locator("table").count(), 8)):
                trs = page.locator("table").nth(i).locator("tr")
                for r in range(trs.count()):
                    cells = trs.nth(r).locator("th,td")
                    vals = [cells.nth(c).inner_text().strip() for c in range(cells.count())]
                    if any(vals):
                        result["rows"].append(vals)
        except Exception as exc:  # noqa: BLE001
            result["error"] = str(exc)
            try:
                page.screenshot(path=str(OUT_DIR / f"vyne_chrome_err_{stamp}.png"), full_page=True)
            except Exception:
                pass
        finally:
            context.close()
            browser.close()

    out = OUT_DIR / f"vyne_eligibility_pull_{stamp}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"ok": result["ok"], "error": result.get("error"), "rows": len(result["rows"]), "finalUrl": result.get("finalUrl"), "bodyHead": (result.get("bodyPreview") or "")[:600], "path": str(out)}, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
