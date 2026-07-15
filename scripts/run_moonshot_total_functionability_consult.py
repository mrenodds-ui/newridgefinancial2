"""Moonshot AI — program review: what is required to make NR2 totally functionable?

Operator: now show moonshot ai the program and what needs to be done to make
this totally functionable
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / ".local_logs" / "moonshot_financial_eval"
DOCS = REPO / "NewRidgeFinancial2" / "docs"
NR2 = REPO / "NewRidgeFinancial2"
OUT.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

CTX = ssl._create_unverified_context()
BASE = os.getenv("NR2_BROWSER", "https://127.0.0.1:8765").rstrip("/")

OPERATOR_REQUEST_VERBATIM = (
    "now show moonshot ai the program and what needs to be done to make "
    "this totally functionable"
)

SYSTEM = """You are Moonshot AI — systems architect for NewRidgeFinancial 2 (NR2)
after the optical clean-slate cutover. CONSULT ONLY — DO NOT APPLY CODE.

Operator (verbatim):
> now show moonshot ai the program and what needs to be done to make this
> totally functionable

CURRENT PROGRAM STATE (trust the LIVE INVENTORY JSON over assumptions):
- Build stamp: nr2-11000-clean · staffRenderMode nr2-clean · packsAllowed false
- Entry: / → 303 → nr2-optical-beam-touch-mockup.html (optical landing)
- Landing schema: nr2-12015-honest-beams (wired, honesty watermark)
- Git main: optical live wire + Apex packs / legacy SPA removed
- Constraints: empty ≠ $0 · no SoftDent write-back · no invent $ · CSP script-src 'self'

WHAT ALREADY WORKS (landing):
- GET /api/browser-session (mutation token)
- GET /api/import-readiness → alignment lasers
- GET /api/softdent/claims-outstanding → SoftDent metric (read-only)
- GET /api/qb/monthly-revenue → QB metric
- POST /api/apex/sync/trigger → Master SYNC
- POST /api/apex/tax/calculate-planning → Tax Prism
- POST /api/hal/evaluate-query → HAL chat page (session required)
- SCRAM demoted DEMO · NO HALT API; Front Desk RBAC disables mutate controls
- Health: db + ollama ok

KNOWN BROKEN / INCOMPLETE (from live probes):
- POST /api/apex/hal/reconciliation → 500 missing apex_reconciliation_pack
- POST /api/apex/softdent/refresh-period → can hang / time out
- nr2_contracts/ MISSING on disk but apex_backend.py imports it (and still refs deleted apex_*_pack modules inside try/except)
- Subpages SoftDent/QB/Claims/Taxes/AR/Narratives/OM/Content are optical theme SHELLS — mostly bind-hint HTML, NOT live-wired (only HAL chat JS is wired)
- HAL evaluate-query can answer money topics dishonestly vs claims API (e.g. claims live $≠0 while chat says 0)
- Film strip / Claims / ERA deep flows not wired on optical surface
- Legacy workstation SPA (hal-core / apex-core / app.js body) removed — optical path only
- SoftDent AR dataset can be STALE (critical soft gap) while lasers show non-blocking green

DEFINITION OF "TOTALLY FUNCTIONABLE" for this consult:
1) Landing controls + metrics always honest under live data / empty / error / locked.
2) Every Pages Hub subpage that shows money or actions is bound to real routes (or clearly UNAVAILABLE, never fake $).
3) Mutations that purport to run actually complete or fail loudly; no hang without UI timeout.
4) HAL chat never invents dollars; money answers gated by import-readiness + empty≠$0.
5) Reconciliation either restored as a real module OR labeled UNAVAILABLE forever (not pretend COHERENT).
6) Build/docs/contracts coherent: no missing package the backend claims to use.
7) Operators can complete a full SoftDent↔QB financial loop without the old Apex SPA.

DIRECTIVES:
1) Review the LIVE program + inventory honestly.
2) Produce a sequenced backlog to reach TOTALLY FUNCTIONABLE (phases P0–P3).
3) Bindability matrix: landing widgets + each hub subpage — LIVE / PARTIAL / SHELL / DEAD.
4) Call out honesty risks still present.
5) Name concrete APIs/files (prefer existing /api/apex/*, /api/softdent/*, /api/qb/*, /api/hal/*).
6) Recommend next schema stamp only if needed.
7) CONSULT ONLY.

OUTPUT (strict markdown):
# Verdict (functionability %)
## 0. Operator Intent (verbatim)
## 1. What the program is today
## 2. Bindability matrix (landing + pages)
## 3. Blockers to totally functionable
## 4. Sequenced plan (P0 blocker / P1 must / P2 should / P3 polish) — concrete tasks
## 5. Honesty risks still open
## 6. Executive Summary (5 bullets)
## 7. Approval checklist (checkboxes for operator)
"""


def _load_dotenv() -> None:
    for path in (REPO / ".env", NR2 / ".env"):
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, _, val = line.partition("=")
                name = name.strip()
                val = val.strip().strip("'").strip('"')
                if name and val and not os.getenv(name):
                    os.environ[name] = val
        except OSError:
            pass


def resolve_api_and_endpoint() -> tuple[str, str, str]:
    _load_dotenv()
    candidates = (
        ("MOONSHOT_API_KEY", os.getenv("MOONSHOT_API_KEY", "").strip()),
        ("OPENROUTER_API_KEY", os.getenv("OPENROUTER_API_KEY", "").strip()),
        ("KIMI_K2_API_KEY", os.getenv("KIMI_K2_API_KEY", "").strip()),
    )
    key_name, api_key = "", ""
    for name, val in candidates:
        if val and len(val) >= 20:
            key_name, api_key = name, val
            break
    if not api_key:
        for name, val in candidates:
            if val:
                key_name, api_key = name, val
                break
    base = (
        os.getenv("MOONSHOT_API_BASE") or os.getenv("KIMI_K2_BASE_URL") or ""
    ).strip()
    if not base:
        if key_name == "MOONSHOT_API_KEY" or (api_key or "").startswith("sk-nv"):
            base = "https://api.moonshot.ai/v1/chat/completions"
        else:
            base = "https://openrouter.ai/api/v1/chat/completions"
    if not base.endswith("/chat/completions"):
        base = base.rstrip("/") + "/chat/completions"
    return key_name, api_key, base


def extract_message_content(raw: dict) -> str:
    try:
        choices = raw.get("choices") or []
        if not choices:
            return ""
        msg = (choices[0] or {}).get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text") or ""))
                elif isinstance(block, str):
                    parts.append(block)
            return "\n".join(p for p in parts if p)
        return str(content or "")
    except Exception:
        return ""


def fetch(url: str, limit: int = 10000) -> str:
    try:
        with urllib.request.urlopen(url, timeout=20, context=CTX) as resp:
            return resp.read().decode("utf-8", "replace")[:limit]
    except Exception as exc:  # noqa: BLE001
        return f"[fetch failed: {exc}]"


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No API key", file=sys.stderr)
        return 1
    if (api_key or "").startswith("sk-nv") or key_name == "MOONSHOT_API_KEY":
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    elif "moonshot.ai" in (base_url or "").lower():
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    else:
        model = str(
            os.getenv("MOONSHOT_MODEL")
            or os.getenv("KIMI_K2_MODEL")
            or "moonshotai/kimi-k2.5"
        ).strip()
    print(f"Using {key_name} @ {base_url} model={model}", flush=True)

    inv_path = REPO / ".local_logs" / "moonshot_functionability_inventory.json"
    inventory: dict = {}
    if inv_path.is_file():
        try:
            inventory = json.loads(inv_path.read_text(encoding="utf-8"))
        except Exception:
            inventory = {}

    prior = DOCS / "MOONSHOT_OPTICAL_MOCKUP_IMPROVE_WORKABILITY_2026-07-15.md"
    prior_txt = ""
    if prior.is_file():
        prior_txt = prior.read_text(encoding="utf-8", errors="replace")[:6000]

    landing_html = fetch(f"{BASE}/nr2-optical-beam-touch-mockup.html", 9000)
    hub_html = fetch(f"{BASE}/nr2-optical-pages-hub.html", 5000)
    softdent_html = fetch(f"{BASE}/nr2-optical-page-softdent.html", 4000)
    qb_html = fetch(f"{BASE}/nr2-optical-page-quickbooks.html", 4000)
    claims_html = fetch(f"{BASE}/nr2-optical-page-claims.html", 3500)
    landing_js = fetch(f"{BASE}/nr2-optical-beam-touch.js", 8000)
    hal_js = fetch(f"{BASE}/nr2-optical-page-hal.js", 4000)

    wire_summary = {
        "landingJsRoutes": [
            "GET /api/browser-session",
            "GET /api/import-readiness",
            "GET /api/softdent/claims-outstanding",
            "GET /api/qb/monthly-revenue",
            "POST /api/apex/sync/trigger",
            "POST /api/apex/softdent/refresh-period",
            "POST /api/apex/hal/reconciliation",
            "POST /api/apex/tax/calculate-planning",
        ],
        "halPageJsRoutes": [
            "GET /api/browser-session",
            "POST /api/hal/evaluate-query",
        ],
        "subpageJsWired": False,
        "commits": [
            "d92bb22 Wire optical landing to live APIs with money honesty (nr2-12015)",
            "5228e0e Remove Apex packs and legacy SPA for nr2-11000-clean cutover",
        ],
    }

    live = {
        "operatorAsk": OPERATOR_REQUEST_VERBATIM,
        "base": BASE,
        "wireSummary": wire_summary,
        "inventory": inventory,
        "honesty": {
            "emptyNotZero": True,
            "noSoftDentWriteBack": True,
            "landingLiveWired": True,
            "subpagesMostlyShells": True,
            "nr2ContractsMissing": True,
            "reconPackMissing": True,
            "halChatCanDisagreeWithClaimsApi": True,
        },
    }

    user = (
        f"OPERATOR REQUEST (verbatim):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        f"LIVE PROGRAM INVENTORY:\n```json\n{json.dumps(live, indent=2)[:14000]}\n```\n\n"
        f"PRIOR WORKABILITY DOC (excerpt):\n```md\n{prior_txt}\n```\n\n"
        f"LANDING HTML (truncated):\n```html\n{landing_html}\n```\n\n"
        f"LANDING JS (truncated):\n```js\n{landing_js}\n```\n\n"
        f"HUB HTML (truncated):\n```html\n{hub_html}\n```\n\n"
        f"SOFTDENT PAGE HTML (truncated):\n```html\n{softdent_html}\n```\n\n"
        f"QB PAGE HTML (truncated):\n```html\n{qb_html}\n```\n\n"
        f"CLAIMS PAGE HTML (truncated):\n```html\n{claims_html}\n```\n\n"
        f"HAL PAGE JS (truncated):\n```js\n{hal_js}\n```\n\n"
        "Show the program clearly and list exactly what must be done to make "
        "it TOTALLY FUNCTIONABLE. Return markdown REPORT only."
    )

    body = {
        "model": model,
        "temperature": 1,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if "openrouter.ai" in base_url:
        headers["HTTP-Referer"] = (
            os.getenv("OPENROUTER_HTTP_REFERER") or "https://127.0.0.1:8765/"
        )
        headers["X-Title"] = (
            os.getenv("OPENROUTER_X_TITLE") or "NR2 Moonshot Total Functionability"
        )

    req = urllib.request.Request(
        base_url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=420, context=CTX) as resp:
            raw = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001
        print(f"Moonshot call failed: {exc}", file=sys.stderr)
        return 2

    text = extract_message_content(raw) or ""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = OUT / f"moonshot_total_functionability_{stamp}.json"
    md_path = DOCS / f"MOONSHOT_TOTAL_FUNCTIONABILITY_{DATE}.md"
    raw_path.write_text(json.dumps(raw, indent=2)[:500000], encoding="utf-8")

    header = (
        f"# Moonshot AI — Total Functionability Plan (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Script:** `scripts/run_moonshot_total_functionability_consult.py`\n"
        f"**Base:** `{BASE}`\n"
        f"**Inventory:** `.local_logs/moonshot_functionability_inventory.json`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    md_path.write_text(header + text.strip() + "\n", encoding="utf-8")
    print("Wrote", md_path, flush=True)
    print("Raw", raw_path, flush=True)
    sys.stdout.buffer.write((text[:4500] + "\n").encode("utf-8", "replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
