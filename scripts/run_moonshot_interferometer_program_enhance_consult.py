"""Moonshot AI — remind program properties/actions; enhance Optical Interferometer.

Operator: remind moonshot what all the property and actions of the program are for
and see if he can enhance it
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
SITE = NR2 / "site"
OUT.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

CTX = ssl._create_unverified_context()
BASE = os.getenv("NR2_BROWSER", "https://127.0.0.1:8765").rstrip("/")

OPERATOR_REQUEST_VERBATIM = (
    "remind moonshot what all the property and actions of the program are for "
    "and see if he can enhance it"
)

PROGRAM_MAP = r'''
# NR2 Property & Action Map (AUTHORITATIVE REMINDER)

Live BUILD applied: nr2-11000-clean (clean-slate; no apex packs).
Design mockups under consultation: nr2-12000/12001 Optical Interferometer.

## Programs
- SoftDent: clinical PMS — production, collections, AR aging, claims, daysheet/register, operatory
- QuickBooks: GL — revenue, P&L, expenses; optional payroll/AP (empty≠$0)
- HAL: local AI agent; board actions; NEVER invents KPI/$/write-offs
- ERA-835: remittance ingest (read-only; no SoftDent write-back)
- Import inbox: document_inbox/softdent + quickbooks
- Unified DB: additive practice health mirror

## Roles / capabilities (RBAC)
front_desk, hygienist, office_manager, dentist, admin
OM: read_financial, write_posting, override_import, manage_ocr, read_ar, cloud_hal,
    approve_writeoff_tier1 (≤$250), read_patient_dossier
dentist: read_all, approve_closeout, approve_writeoff_tier2, …

## Staff page purposes
financial — owner KPIs / production / collections / import health
softdent — clinical practice / collections gap / ERA / aging
quickbooks — GL / expenses / payroll-AP honesty
claims — kanban / aging / denials / critical actions
ar — SoftDent AR waterfall / unapplied
taxes — EBITDA / C0 guidance / scenarios / filing
content/documents/library/narratives — docs & clinical narratives
office-manager — huddle / operatory / recall / EOB backlog
hal — import health + program posture spine

## Critical actions (what they are FOR)
POST /api/apex/sync/trigger — pull SoftDent+QB imports into cache (single-flight)
POST /api/apex/softdent/refresh-period — promote Register/Daysheet from SoftDentReportExports
POST /api/apex/sync/qb-payroll-ap-export — drop payroll/AP CSVs (honest empty ok)
POST /api/apex/hal/board-actions — sync_imports, refresh_softdent_period, navigate, focus_widget…
POST /api/apex/hal/era835-ingest + era-inbox/* — remittance discover/ingest
POST /api/apex/hal/reconciliation — SoftDent×QuickBooks recon status/run
POST /api/apex/hal/import-quarantine* — release/retry/purge poisoned imports
POST /api/apex/hal/cache-warm — warm HAL/import caches
POST /api/apex/hal/health-audit / deep-audit — practice health classify
POST /api/apex/narratives/generate — clinical narrative drafts (no invented findings)
POST /api/apex/tax/calculate-planning + scenarios — tax/EBITDA planning only
GET /api/import-readiness + /api/app-info — completeness, blocking vs soft gaps, role/caps
GET /api/apex/widgets/<page> — honesty-empty widget payloads
POST /api/hal/evaluate-query — Ask HAL local (cloud denied by default)

## Import datasets
CRITICAL: softdent.dashboard, softdent.ar (120m), quickbooks.revenue, quickbooks.profitAndLoss
WARNING/optional: claims, expenses, categories, QB AR, payroll, AP, clinical notes, etc.
Blocking = critical missing/empty. Soft gaps = optional/stale honesty only (not 403).

## Honesty laws
empty ≠ $0 · stale AR tombstones money reads · no SoftDent write-back · HAL refuses invent write-offs

## Interferometer so far
Emitters SoftDent/QB/HAL → core interferometer; broken beam = stale;
addons: diffraction grating, polarizers, film plate, phase-conjugate mirror, vacuum gauges
'''

SYSTEM = """You are Moonshot AI — principal systems designer for NR2 Optical Interferometer.

Operator:
> remind moonshot what all the property and actions of the program are for and see if he can enhance it

You will receive an AUTHORITATIVE property/action map. Treat it as ground truth.
Your prior interferometer + spectral add-ons were visually strong but UNDER-MAPPED
to real program surface area (claims, taxes, narratives, quarantine, ERA, RBAC,
board actions, pages beyond SD/QB/HAL emitters).

YOUR JOB:
1) Re-ground: briefly restate what the major properties/actions are FOR (in your words)
2) Gap analysis: what of NR2 is still invisible on the interferometer bench
3) ENHANCE the Optical Interferometer so it can express / trigger the real program —
   without abandoning the optical metaphor or resurrecting Bloomberg mosaics/apex packs
4) Map concrete actions (sync, refresh-period, ERA ingest, quarantine, recon, Ask HAL,
   navigate to claims/taxes/OM, etc.) onto optical affordances (emitters, dials, plates,
   core modes, SCRAM semantics, etc.)
5) Honesty + RBAC: show how capabilities gate what staff can fire from the bench

CONSULT / DESIGN ONLY. empty ≠ $0; never invent SoftDent dollars; no SoftDent write-back.

OUTPUT (strict markdown):
# Verdict (enhanced concept name + schema stamp recommendation)
## 0. Operator Intent (verbatim)
## 1. Program reminder — what properties & actions are FOR (tight)
## 2. Coverage gaps vs current interferometer
## 3. Enhancement thesis (how the bench becomes the program control surface)
## 4. Action→optic map (table: action → control → feedback → honesty rule)
## 5. Emitter / optic expansions (claims, taxes, ERA, quarantine, OM — without clutter)
## 6. Updated schema (keep 12001 or bump 12002 — justify)
## 7. Mockup instructions (what to add to addons mockup)
## 8. Acceptance criteria
## 9. Executive Summary (7 bullets)
## 10. Approval checklist
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
    print(f"Using {key_name} @ {base_url} model={model}")

    prior_bits = []
    for name in (
        f"MOONSHOT_OPTICAL_INTERFEROMETER_ADDONS_{DATE}.md",
        f"MOONSHOT_WALLSTREET_FINANCIAL_IMAGINATIVE_{DATE}.md",
    ):
        p = DOCS / name
        if p.is_file():
            prior_bits.append(f"### {name}\n{p.read_text(encoding='utf-8', errors='replace')[:5000]}")

    build = {}
    try:
        build = json.loads((NR2 / "nr2-build.json").read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        build = {"error": str(exc)}

    live = {
        "operatorAsk": OPERATOR_REQUEST_VERBATIM,
        "currentBuild": build,
        "mockups": {
            "v1": f"{BASE}/nr2-optical-interferometer-mockup.html",
            "addons": f"{BASE}/nr2-optical-interferometer-addons-mockup.html",
        },
    }

    user = (
        f"OPERATOR REQUEST (verbatim):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        f"LIVE:\n```json\n{json.dumps(live, indent=2)}\n```\n\n"
        f"PROGRAM MAP:\n{PROGRAM_MAP}\n\n"
        + ("PRIOR INTERFEROMETER DOCS:\n" + "\n\n".join(prior_bits) if prior_bits else "")
        + "\n\nRemind yourself of the program, then ENHANCE the interferometer. "
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
            os.getenv("OPENROUTER_X_TITLE") or "NR2 Moonshot Program-Aware Enhance"
        )

    req = urllib.request.Request(
        base_url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=700, context=CTX) as resp:
            raw = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001
        print(f"Moonshot call failed: {exc}", file=sys.stderr)
        return 2

    text = extract_message_content(raw) or ""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = OUT / f"moonshot_interferometer_program_enhance_{stamp}.json"
    md_path = DOCS / f"MOONSHOT_OPTICAL_INTERFEROMETER_PROGRAM_ENHANCE_{DATE}.md"
    raw_path.write_text(json.dumps(raw, indent=2)[:500000], encoding="utf-8")

    header = (
        f"# Moonshot AI — Program-Aware Interferometer Enhancement (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Script:** `scripts/run_moonshot_interferometer_program_enhance_consult.py`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    md_path.write_text(header + text.strip() + "\n", encoding="utf-8")
    print("Wrote", md_path)
    print("Raw", raw_path)
    print(text[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
