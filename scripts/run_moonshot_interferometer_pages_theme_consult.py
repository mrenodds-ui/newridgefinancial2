"""Moonshot AI — widget bindability + full program pages/subpages same optical theme.

Operator: ask moonshot ai if all these widgets will work and have him create
pages and subpages with all that is required of this program. tell him to
follow the same theme as the main page
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
    "ask moonshot ai if all these widgets will work and have him create "
    "pages and subpages with all that is required of this program. tell him "
    "to follow the same theme as the main page"
)

PROGRAM = """
RUNTIME BUILD: nr2-11000-clean (clean-slate shell — real pages not wired yet).
OPTICAL MAIN MOCKUP: nr2-12009-interference
  HAL center AI core · SoftDent left-bottom white pulse · QuickBooks right ·
  Tax Prism upper-right · Master Pulse sync · Period Wheel · Reconcile ·
  Claims/Narrative/ERA/Quarantine removed from MAIN surface.

APEX PAGE IDs still required by program backend:
  financial, softdent, quickbooks, ar, claims, taxes, narratives, documents,
  library, office-manager, content, hal

KEY APIs (must bind or DEFER honestly):
  POST /api/apex/sync/trigger
  POST /api/apex/softdent/refresh-period
  POST /api/apex/hal/reconciliation
  POST /api/apex/tax/calculate-planning
  POST /api/apex/sync/qb-payroll-ap-export
  GET  /api/import-readiness
  POST /api/apex/hal/board-actions
  SoftDent ledger / AR / claims / ERA (read-only, no write-back)
  Narratives generate, quarantine release, etc. — may live on SUBPAGES not main

RBAC: front_desk, hygienist, office_manager, dentist, admin
HONESTY: empty≠$0; no SoftDent write-back; no invent $; critical blocking gaps
THEME: Optical interferometer — vacuum black, SoftDent/QB/HAL beams, emitters,
  HAL spectral core, readable type, no ornamental unbound widgets
"""

SYSTEM = """You are Moonshot AI — architect/designer of NR2 Optical Interferometer
(schema nr2-12009-interference main financial bench).

Operator (verbatim):
> ask moonshot ai if all these widgets will work and have him create pages
> and subpages with all that is required of this program. tell him to follow
> the same theme as the main page

DIRECTIVES (mandatory):
1) **Widget workability audit** of EVERY control on the current main mockup
   (SoftDent emitter, QuickBooks emitter, Tax Prism emitter, HAL core,
   Master Pulse/SYNC, Period Wheel, RECONCILE, RBAC roles, SCRAM, film strip,
   alignment lasers). For each: Bindable / Needs subpage / Cut — cite APIs.
2) **Full program page + subpage tree** covering all required NR2 surfaces
   (financial hub, SoftDent, QuickBooks, AR, claims, taxes, narratives,
   documents, library, office-manager, HAL, import/sync health). Same optical
   theme language as main page (HAL center presence or beam branding,
   emitter housings, vacuum honesty, readable type).
3) Specify navigation: how operators leave main bench into sub-benches
   without losing theme or honesty.
4) Each page lists: purpose, primary widgets, SoftDent/QB/HAL binds, RBAC.
5) Call out what lives OFF the main page (ERA, Claims kanban, Narratives,
   Quarantine) so main stays clean but program stays complete.
6) CONSULT / DESIGN ONLY — do not claim production apply. Propose schema bump
   for page-system stamp (e.g. nr2-12010-pages).

OUTPUT (strict markdown):
# Verdict (schema stamp)
## 0. Operator Intent (verbatim)
## 1. Main-page widget workability matrix (table)
## 2. Gaps / deferred to subpages
## 3. Full page + subpage tree (sitemap)
## 4. Per-page briefs (each page: widgets, binds, theme notes)
## 5. Navigation / shell chrome (same theme)
## 6. Implementation order (phased)
## 7. Schema bump justification
## 8. Executive Summary (7 bullets)
## 9. Approval checklist
DO NOT APPLY CODE.
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

    prior = DOCS / f"MOONSHOT_OPTICAL_INTERFEROMETER_QB_RIGHT_SD_LEFT_{DATE}.md"
    prior_txt = ""
    if prior.is_file():
        prior_txt = prior.read_text(encoding="utf-8", errors="replace")[:3500]

    live = {
        "operatorAsk": OPERATOR_REQUEST_VERBATIM,
        "mainMockup": f"{BASE}/nr2-optical-qb-right-sd-left-mockup.html",
        "schemaConsult": "nr2-12009-interference",
        "runtimeBuild": "nr2-11000-clean",
    }

    user = (
        f"OPERATOR REQUEST (verbatim):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        f"PROGRAM FACTS:\n{PROGRAM}\n\n"
        f"LIVE:\n```json\n{json.dumps(live, indent=2)}\n```\n\n"
        + (f"PRIOR MAIN LAYOUT:\n{prior_txt}\n\n" if prior_txt else "")
        + "Audit widgets. Design full pages/subpages same optical theme. "
        "Return markdown REPORT only. CONSULT ONLY."
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
            os.getenv("OPENROUTER_X_TITLE") or "NR2 Moonshot Full Pages Theme"
        )

    req = urllib.request.Request(
        base_url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=500, context=CTX) as resp:
            raw = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001
        print(f"Moonshot call failed: {exc}", file=sys.stderr)
        return 2

    text = extract_message_content(raw) or ""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = OUT / f"moonshot_interferometer_pages_theme_{stamp}.json"
    md_path = DOCS / f"MOONSHOT_OPTICAL_INTERFEROMETER_PAGES_THEME_{DATE}.md"
    raw_path.write_text(json.dumps(raw, indent=2)[:500000], encoding="utf-8")

    header = (
        f"# Moonshot AI — Widget Workability + Full Pages/Subpages "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Script:** `scripts/run_moonshot_interferometer_pages_theme_consult.py`\n"
        f"**Apply:** DO NOT APPLY production cutover until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    md_path.write_text(header + text.strip() + "\n", encoding="utf-8")
    print("Wrote", md_path, flush=True)
    print("Raw", raw_path, flush=True)
    sys.stdout.buffer.write((text[:2800] + "\n").encode("utf-8", "replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
