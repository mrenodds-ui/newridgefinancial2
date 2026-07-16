"""Trellis pull v3 — reuse v1 login that worked; wait longer; dump appointments DOM + APIs."""

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
STATE = OUT_DIR / "vyne_storage_state.json"


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
        "links": [],
        "error": "",
        "finalUrl": "",
        "apiHits": 0,
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1440, "height": 960},
            storage_state=str(STATE) if STATE.is_file() else None,
        )
        page = context.new_page()

        def on_response(resp) -> None:
            try:
                u = resp.url.lower()
                if resp.status >= 400:
                    return
                if not any(k in u for k in ("elig", "benefit", "appoint", "coverage", "patient", "claim")):
                    return
                ctype = (resp.headers.get("content-type") or "").lower()
                if "json" not in ctype:
                    return
                text = resp.text()
                if not text or len(text) > 1_500_000:
                    return
                api_hits.append({"url": resp.url, "status": resp.status, "json": json.loads(text)})
            except Exception:
                return

        page.on("response", on_response)

        try:
            page.goto("https://app.vynetrellis.com", wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(2000)

            if page.get_by_label("Email").count():
                page.get_by_label("Email").fill(user)
                page.get_by_label("Password").fill(password)
                page.get_by_role("button", name="Continue").click()
                page.wait_for_timeout(3500)

            if page.get_by_text("Select an organization").count():
                page.locator("li.ant-list-item, [class*='locationItem']").filter(
                    has_text="Michael Christian Reno"
                ).first.click()
                page.wait_for_timeout(6000)

            # Ensure app shell
            for _ in range(40):
                if "app.vynetrellis.com" in page.url and "authenticate" not in page.url:
                    break
                page.wait_for_timeout(500)
            else:
                raise RuntimeError(f"did not reach app shell: {page.url}")

            context.storage_state(path=str(STATE))
            page.goto("https://app.vynetrellis.com/appointments", wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(8000)
            result["finalUrl"] = page.url
            page.screenshot(path=str(OUT_DIR / f"vyne_appts_{stamp}.png"), full_page=True)

            # Collect nav / link labels
            for a in page.locator("a,button,[role='tab']").all()[:80]:
                try:
                    t = a.inner_text().strip()
                    if t:
                        result["links"].append(t[:120])
                except Exception:
                    pass

            # Prefer Eligibility
            for pat in (r"Eligibility", r"Benefits", r"Clear ?Coverage"):
                loc = page.get_by_text(re.compile(pat, re.I))
                if loc.count():
                    try:
                        loc.first.click(timeout=4000)
                        page.wait_for_timeout(5000)
                        break
                    except Exception:
                        continue

            page.screenshot(path=str(OUT_DIR / f"vyne_after_nav_{stamp}.png"), full_page=True)
            body = page.locator("body").inner_text(timeout=15000)
            result["bodyPreview"] = body[:12000]

            # rows from tables + role=row
            for i in range(min(page.locator("table").count(), 10)):
                trs = page.locator("table").nth(i).locator("tr")
                for r in range(trs.count()):
                    cells = trs.nth(r).locator("th,td")
                    vals = [cells.nth(c).inner_text().strip() for c in range(cells.count())]
                    if any(vals):
                        result["rows"].append(vals)
            for i in range(min(page.locator("[role='row']").count(), 100)):
                t = page.locator("[role='row']").nth(i).inner_text().strip()
                if t:
                    result["rows"].append([t])

            result["apiHits"] = len(api_hits)
            result["ok"] = True
        except Exception as exc:  # noqa: BLE001
            result["error"] = str(exc)
            result["finalUrl"] = page.url
            try:
                page.screenshot(path=str(OUT_DIR / f"vyne_error_{stamp}.png"), full_page=True)
                result["bodyPreview"] = page.locator("body").inner_text()[:4000]
            except Exception:
                pass
        finally:
            context.close()
            browser.close()

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
                    "links": (result.get("links") or [])[:30],
                    "path": str(out),
                    "finalUrl": result.get("finalUrl"),
                    "bodyHead": (result.get("bodyPreview") or "")[:500],
                },
                indent=2,
            )
        )
        return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
