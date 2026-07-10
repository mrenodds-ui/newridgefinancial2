"""Moonshot AI — SoftDent/QB import health, HAL programming, widget health, CPA-style tax/EBITDA UX (CONSULT ONLY).

Operator request is passed VERBATIM. Do not rewrite operator intent.
Does NOT apply any code.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / ".local_logs" / "moonshot_financial_eval"
DOCS = REPO / "NewRidgeFinancial2" / "docs"
OUT.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

HELPER = (
    REPO
    / "_archive"
    / "2026-07-10"
    / ".local_logs"
    / "moonshot_financial_eval"
    / "_run_moonshot_eval.py"
)
sys.path.insert(0, str(HELPER.parent))
from _run_moonshot_eval import extract_message_content, resolve_api_and_endpoint  # noqa: E402

OPERATOR_REQUEST_VERBATIM = """
ask moonshot ai about my quickbooks and softdent imports, are they healthy, recommendations, ask about hal programming, ask him if all widgets are healthy and have imports from hal, any other recommendations to make the tax page more interactive and Ebitda interactive with sliding widget, how to make those pages function like a cpa would use.
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — CPA-aware product architect + HAL systems engineer
for NewRidge Financial 2.0 (NR2), a local HTTPS Apex starship-bridge app for a Kansas dental S-corp.

CRITICAL CONSTRAINTS:
1. Answer ALL parts of the operator request (do not rewrite their wording):
   (A) SoftDent + QuickBooks import health assessment + recommendations.
   (B) HAL programming (current board-control + what to improve).
   (C) Are ALL widgets healthy and fed by imports / HAL? (honest gaps).
   (D) Make Taxes page more interactive; make EBITDA interactive with a SLIDING widget.
   (E) How to make Taxes + EBITDA pages function like a CPA would use them.
2. CONSULT ONLY — DO NOT APPLY / DO NOT CODE until operator approves.
3. Live build reviewed: **hal-10310**. Use LIVE FACTS in the user context as ground truth for health.
4. Hard rules: never invent financial dollar amounts; planning tax ≠ filed return; CPA review required;
   HAL must not invent $ into widgets (sync/focus/suggest only).
5. Distinguish: import-backed book numbers vs planning estimates vs CPA-filed returns.
6. For sliding EBITDA: propose native Apex scrubber/slider UX (add-backs, owner salary adjustment bands)
   that only adjusts labeled planning inputs — not inventing SoftDent/QB history.
7. Rank MUST / SHOULD / NICE; phased plan with validation gate.
8. Provide paste-ready specs labeled CONSULT ONLY.

OUTPUT FORMAT (strict markdown):
# Verdict
## 0. Operator Intent (quote; confirm consult-only)
## 1. SoftDent + QuickBooks Import Health
Healthy? Evidence from live facts; gaps; recommendations ranked.
## 2. HAL Programming Assessment
What exists at hal-10310; gaps; recommended programming next steps.
## 3. Widget Health & Import/HAL Coverage
Per-page honesty: which widgets are import-fed, empty, HAL-driven; are ALL healthy?
## 4. Taxes Page — More Interactive (CPA workflow)
## 5. EBITDA — Interactive Sliding Widget
Concept, slider controls, data contract, honesty rules.
## 6. CPA-Grade Page Behavior (Taxes + EBITDA)
Workflow a CPA would expect (workpapers, bridge, estimates, returns library, sign-off).
## 7. Moonshot Spec Deliverables (CONSULT ONLY)
## 8. Implementation Phases (C0 validate → Cn) + Validation Gate
DO NOT APPLY until operator says proceed / validated / approve.
## 9. Risks, CPA disclaimer & Rollback
"""


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 20),
    ("NewRidgeFinancial2/docs/MOONSHOT_HAL_BOARD_CONTROL_APPLIED_2026-07-10.md", 50),
    ("NewRidgeFinancial2/docs/MOONSHOT_DESKTOP_HAL_TAX_EBITDA_APPLIED_2026-07-10.md", 60),
    ("NewRidgeFinancial2/tax_engine.py", 80),
]


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} lines truncated]"


def build_context() -> str:
    parts: list[str] = []
    for rel, max_lines in CONTEXT_FILES:
        path = REPO / rel
        if not path.is_file():
            parts.append(f"### FILE: {rel}\n(missing)")
            continue
        body = _truncate(path.read_text(encoding="utf-8", errors="replace"), max_lines)
        ext = path.suffix.lstrip(".") or "txt"
        parts.append(f"### FILE: {rel}\n```{ext}\n{body}\n```")
    parts.append(
        """### LIVE FACTS (hal-10310 — captured at consult time)
- Import mode: direct-first
- Diagnostics summary: total=16, connected=16, partial=0, stale=0, missing=0
- Freshness: Imports fresh 16/16
- SoftDent rows: dashboard=2, ar=4, claims=60, claimStatus=60, procedures=62, newPatients=1, operatory=0
- QuickBooks rows: profitAndLoss=1, revenue=1, expenses=1, expenseCategories=8, ar=4
- Known thin spots: collectionsPending on latest SoftDent period; insurance/patient often 0.0; procedures Provider often single label; operatory empty; tax returns library empty until operator uploads
- HAL board control (10310): sync_imports, refresh_page, navigate, focus/highlight widget, categorize assist open, import status banner — never invents $
- Taxes page already: book net, federal/KS planning KPIs, book-to-tax waterfall, EBITDA waterfall, scrubber, CPA banner
- EBITDA: management walk from QB net + dep/interest when present in expenseCategories
- Widget empty_status counts (status==empty): financial 1, taxes 1, softdent 1, qb 0, ar 0, claims 0, hal 1, documents 1, office-mgr 0
- Operator asks: import health + recommendations; HAL programming; widget health / imports from HAL; tax + EBITDA more interactive with sliding widget; CPA-like page function.
- CONSULT ONLY — report; do not code until approve.
"""
    )
    return "\n\n".join(parts)


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No Moonshot/OpenRouter API key.", file=sys.stderr)
        return 1

    if "moonshot" in (base_url or "").lower():
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    else:
        model = str(
            os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2"
        ).strip()

    print(f"Using {key_name} @ {base_url} model={model}")
    user = (
        "OPERATOR REQUEST (VERBATIM — do not rewrite):\n\n"
        f"{OPERATOR_REQUEST_VERBATIM}\n\n"
        "CONSULT ONLY — report assessment + recommendations. Do not apply code.\n\n"
        "## Context\n\n"
        + build_context()
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 16000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Import Health Tax EBITDA CPA Consult"

    print("Calling Moonshot AI (consult only — will not apply)...")
    req = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3600) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = extract_message_content(body)
        status = "ok"
    except urllib.error.HTTPError as exc:
        content = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:4000]}"
        status = f"HTTP {exc.code}"
    except Exception as exc:
        content = str(exc)
        status = "error"

    header = (
        f"# Moonshot AI — Import Health, HAL Programming, Widget Health, CPA Tax/EBITDA UX (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10310  \n"
        f"**Script:** `scripts/run_moonshot_import_health_cpa_tax_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_IMPORT_HEALTH_CPA_TAX_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_IMPORT_HEALTH_CPA_TAX_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
