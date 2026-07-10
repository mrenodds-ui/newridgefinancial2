"""Moonshot AI — Desktop icon, HAL↔widgets, SoftDent/QB sync verify, S-corp tax+EBITDA+returns (CONSULT ONLY).

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
now ask moonshot ai how to make a desktop icon, hook up hal to all widgets, sync data and verify they work with softdent and quickbooks, also I need high tech programming to calculate taxes for the federal and kanas for a s-corp as well as calulating EBITDA.  I need a place to download previous tax returns for EBITDA, too.
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — product architect + systems engineer for
NewRidge Financial 2.0 (NR2), a local HTTPS Bottle browser app (Apex starship bridge) for a
Kansas dental practice S corporation.

CRITICAL CONSTRAINTS:
1. Answer ALL parts of the operator request (keep their wording; "kanas" = Kansas):
   (A) How to make a desktop icon (Windows) to launch NR2.
   (B) Hook HAL up to ALL widgets (explain/ask/context per instrument).
   (C) Sync data and VERIFY SoftDent + QuickBooks imports work end-to-end.
   (D) High-tech programming to calculate FEDERAL + KANSAS taxes for an S-corp.
   (E) Calculating EBITDA (practice / owner-normalized).
   (F) A place to download previous tax returns (for EBITDA / tax context).
2. Do not rewrite the operator's request — treat their wording as source of truth.
3. CONSULT ONLY — DO NOT APPLY / DO NOT CODE into the live app until operator approves.
4. Current live build: NR2-Apex **hal-10290** at https://127.0.0.1:8765/ via StartProgram.bat / scripts/start_nr2_browser.ps1.
5. Existing pieces to EXTEND (do not invent parallel stacks):
   - Launchers: StartProgram.bat, scripts/start_program.ps1, scripts/start_nr2_browser.ps1
   - Sync: document inbox app_data/nr2/document_inbox/{softdent,quickbooks}/, Sync-HAL-Imports.ps1, /api/sync-documents, Apex sync button
   - Tax: NewRidgeFinancial2/tax_engine.py already does S-corp federal+Kansas PLANNING rates + book-to-tax bridge + quarterly estimates from QB net income — planning only, CPA review required; never invent dollars
   - HAL: /api/hal/evaluate-query, apex-hal-bridge, neural core; widgets via /api/apex/widgets/<page>
   - Documents page exists; tax returns would be local files in inbox/library — no cloud tax-prep OAuth
6. Hard rules: never invent financial dollar amounts; honest empty states; no third-party bank OAuth / TradingView embeds; wipe-safe (no resurrecting moonshot-mockup).
7. Tax/EBITDA guidance must distinguish: import-backed book numbers vs planning estimates vs CPA-filed returns. Label planning clearly.
8. Provide concrete Windows desktop-shortcut steps + optional .lnk / PowerShell deliverable.
9. For HAL↔widgets: propose a contract (widget id, page, ask-HAL action, context payload) without inventing metric values.
10. For sync verify: checklist SoftDent sections + QB sections + Apex page smoke tests.
11. Rank MUST / SHOULD / NICE; phased plan with validation gate.

OUTPUT FORMAT (strict markdown):
# Verdict
## 0. Operator Intent (quote; confirm consult-only)
## 1. Desktop Icon (Windows launch)
Steps + optional script/shortcut deliverable; StartProgram.bat path.
## 2. Hook HAL to All Widgets
Architecture, per-widget Ask HAL affordance, context packet schema, pages covered.
## 3. Sync SoftDent + QuickBooks + Verification
Sync path, verify checklist, failure modes, Apex pages that prove each import.
## 4. Federal + Kansas S-Corp Tax Programming (high-tech)
Extend tax_engine vs new modules; federal vs Kansas; what is planning vs filed; UI on Taxes page.
## 5. EBITDA Calculation
Formula from QB/SoftDent imports; add-backs; instruments; honesty rules.
## 6. Previous Tax Returns Download Place
Where in Apex (Documents/Library/Taxes); local storage; upload/list/download; use for EBITDA context — no invented return figures.
## 7. Moonshot Spec Deliverables (paste-ready, CONSULT ONLY)
## 8. Implementation Phases (T0 validate → Tn) + Validation Gate
DO NOT APPLY until operator says proceed / validated / approve.
## 9. Risks, CPA disclaimer & Rollback
"""


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 20),
    ("StartProgram.bat", 20),
    ("NewRidgeFinancial2/tax_engine.py", 100),
    ("NewRidgeFinancial2/README.md", 100),
    ("NewRidgeFinancial2/docs/MOONSHOT_MORE_WIDGETS_FLASH_APPLIED_2026-07-10.md", 60),
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
        """### LIVE FACTS (hal-10290)
- Apex bridge: sidebar, dual tickers, mosaic instruments, HAL neural core, categorize, visual boosts, more-widgets pack.
- tax_engine.py: S-corp, Kansas, federal planning rate 32%, KS 5.7%, book-to-tax bridge, quarterly estimates, ebitda_add_backs param exists but Apex UI may not fully surface EBITDA walk.
- Imports: SoftDent + QuickBooks via document inbox / direct-first; Apex sync button + /api/sync-documents.
- Operator wants: desktop icon; HAL on all widgets; sync+verify SoftDent/QB; high-tech federal+Kansas S-corp tax calc; EBITDA; place to download prior tax returns for EBITDA.
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
        "CONSULT ONLY — report a plan. Do not apply code. Wait for operator approve.\n\n"
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
        headers["X-Title"] = "NR2 Desktop HAL Tax EBITDA Consult"

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
        f"# Moonshot AI — Desktop Icon, HAL↔Widgets, Sync Verify, S-Corp Tax + EBITDA + Returns (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10290  \n"
        f"**Script:** `scripts/run_moonshot_desktop_hal_tax_ebitda_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_DESKTOP_HAL_TAX_EBITDA_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_DESKTOP_HAL_TAX_EBITDA_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
