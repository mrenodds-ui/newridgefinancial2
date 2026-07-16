"""Playwright Trellis pull v2 — login, appointments eligibility, capture API JSON."""

from __future__ import annotations

import json
import os
import re
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
    user = os.environ.get("VYNE_AUTOMATION_USERNAME", "").strip()
    password = os.environ.get("VYNE_AUTOMATION_PASSWORD", "").strip()
    if not user or not password:
        print("Missing credentials", file=sys.stderr)
        return 2

    from playwright.sync_api import sync_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    api_hits: list[dict] = []
    result: dict = {
        "ok": False,
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "rows": [],
        "apiHits": 0,
        "error": "",
        "finalUrl": "",
        "navHints": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        context = browser.new_context(viewport={"width": 1440, "height": 960})
        page = context.new_page()

        def on_response(resp) -> None:
            try:
                u = resp.url
                if resp.status >= 400:
                    return
                if not any(
                    k in u.lower()
                    for k in ("eligib", "benefit", "appointment", "coverage", "clearcoverage", "patient")
                ):
                    return
                ctype = (resp.headers.get("content-type") or "").lower()
                if "json" not in ctype and "javascript" not in ctype:
                    return
                body = resp.text()
                if not body or len(body) > 2_000_000:
                    return
                try:
                    payload = json.loads(body)
                except Exception:
                    return
                api_hits.append({"url": u, "status": resp.status, "payload": payload})
            except Exception:
                return

        page.on("response", on_response)

        try:
            page.goto("https://app.vynetrellis.com", wait_until="networkidle", timeout=120000)
            page.wait_for_timeout(1000)
            if page.get_by_label("Email").count():
                page.get_by_label("Email").fill(user)
                page.get_by_label("Password").fill(password)
                page.get_by_role("button", name="Continue").click()
                page.wait_for_timeout(3000)
            if page.get_by_text("Select an organization").count():
                page.get_by_text("Michael Christian Reno DDS PA").first.click()
                page.wait_for_timeout(5000)

            # Land on appointments
            page.goto("https://app.vynetrellis.com/appointments", wait_until="networkidle", timeout=120000)
            page.wait_for_timeout(3000)
            result["finalUrl"] = page.url
            page.screenshot(path=str(OUT_DIR / f"vyne_appts_{stamp}.png"), full_page=True)

            # Click Eligibility-like controls
            for pattern in (
                r"Eligibility",
                r"Benefits",
                r"ClearCoverage",
                r"Verify",
                r"Insurance",
            ):
                loc = page.get_by_text(re.compile(pattern, re.I))
                cnt = loc.count()
                result["navHints"].append({"pattern": pattern, "count": cnt})
                if cnt:
                    try:
                        loc.first.click(timeout=3000)
                        page.wait_for_timeout(2500)
                    except Exception:
                        pass

            # Tabs
            for name in ("Eligibility", "Benefits", "Appointments"):
                tab = page.get_by_role("tab", name=re.compile(name, re.I))
                if tab.count():
                    try:
                        tab.first.click()
                        page.wait_for_timeout(2500)
                    except Exception:
                        pass

            page.screenshot(path=str(OUT_DIR / f"vyne_elig_{stamp}.png"), full_page=True)
            body = page.locator("body").inner_text(timeout=10000)
            result["bodyPreview"] = body[:8000]

            # Table scrape
            for i in range(min(page.locator("table").count(), 8)):
                table = page.locator("table").nth(i)
                for r in range(table.locator("tr").count()):
                    cells = table.locator("tr").nth(r).locator("th,td")
                    vals = []
                    for c in range(cells.count()):
                        vals.append(cells.nth(c).inner_text().strip())
                    if any(vals):
                        result["rows"].append(vals)

            # Grid / list rows
            for sel in ("[role='row']", ".ant-table-row", "[data-testid*='elig']", "[class*='eligib']"):
                loc = page.locator(sel)
                n = min(loc.count(), 80)
                for i in range(n):
                    t = loc.nth(i).inner_text().strip()
                    if t and len(t) > 8:
                        result["rows"].append([t])

            result["apiHits"] = len(api_hits)
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

    # Persist API payloads separately (may include PHI — app_data gitignored)
    api_path = OUT_DIR / f"vyne_api_{stamp}.json"
    api_path.write_text(json.dumps(api_hits, indent=2, default=str)[:5_000_000], encoding="utf-8")
    result["apiPath"] = str(api_path)
    out = OUT_DIR / f"vyne_eligibility_pull_{stamp}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": result["ok"],
                "error": result.get("error"),
                "rows": len(result.get("rows") or []),
                "apiHits": result.get("apiHits"),
                "path": str(out),
                "apiPath": str(api_path),
                "finalUrl": result.get("finalUrl"),
                "navHints": result.get("navHints"),
            },
            indent=2,
        )
    )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
