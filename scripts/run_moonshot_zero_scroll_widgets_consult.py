"""Moonshot AI — Zero-scroll pages: fix widgets + organize, then report (CONSULT ONLY).

Operator request is passed VERBATIM. Do not rewrite operator intent.
Does NOT apply any code. Await operator approval before coding.
"""

from __future__ import annotations

import json
import os
import sys
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

OPERATOR_REQUEST_VERBATIM = (
    "i dont want to scroll down any page. fix widgets and organuze rhen report"
).strip()

SYSTEM = """You are Moonshot AI — principal UX/systems engineer for NR2 Apex (hal-10560).

Operator message (VERBATIM intent): they do NOT want to scroll down ANY page.
They want widgets FIXED and ORGANIZED, THEN a REPORT.

Context already shipped (do not pretend it did not happen):
- Compact professional pages Phases 1–5 applied (hal-10550): motion kill, empty collapse,
  size/grid normalize_first_viewport, Claims pipeline+kanban subpage, HAL sole-l,
  density toggle. Docs: MOONSHOT_COMPACT_PROFESSIONAL_PAGES_APPLIED_2026-07-11.md
- Inbox sync coherence (hal-10560) landed on branch fix/main-validate-ci (PR not merged yet)
- Operator is still unhappy: pages still require vertical scrolling; widgets still wrong

CONSULT ONLY — DO NOT APPLY CODE. Produce an engineer-grade REPORT that:
1. Diagnoses WHY scroll still exists after compact Phases 1–5 (be blunt; name files/pages)
2. Prescribes a ZERO-SCROLL (or near-zero) FIRST VIEWPORT contract stricter than before
3. Defines FIX + ORGANIZE package: which widgets to resize/reorder/collapse/move to subpages
4. Page-by-page map for: financial, taxes, softdent, quickbooks, ar, claims, narratives,
   documents, library, office-manager, HAL
5. Phased remediation with validation gates (1920×1080: primary work fits without scroll)
6. Honesty: empty ≠ $0; no invented dollars; prefer Apex additive fixes

OUTPUT (strict markdown):
# Verdict
## 0. Operator Intent (quote verbatim; confirm consult-only)
## 1. Why Scroll Still Happens (post-hal-10550)
## 2. Zero-Scroll Contract (hard rules)
## 3. Fix + Organize Package (single recommended work package)
Goal, why now, effort, files, phases, validation gate
## 4. Page-by-Page Widget Map
Table: Page | Offending widgets | Action (resize/reorder/subpage/remove) | Target first viewport
## 5. Report Summary (executive bullets for operator)
## 6. Approval checklist
DO NOT APPLY CODE.
"""


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No API key", file=sys.stderr)
        return 1
    model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    if "moonshot" not in (base_url or "").lower():
        model = str(
            os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2"
        ).strip()
    print(f"Using {key_name} @ {base_url} model={model}")
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Tell Moonshot: operator refuses vertical page scroll. Fix widgets, organize them, "
        "then report. CONSULT ONLY — produce the report/plan; do not code.\n\n"
        "### Live context\n"
        "- Build: hal-10560\n"
        "- Compact pages already applied once; operator still scrolls → prior pass insufficient\n"
        "- Need stricter zero-scroll first-viewport + reorganize remaining tall widgets\n"
        "- Branch fix/main-validate-ci has unmerged Expert SE + compact + inbox coherence\n"
        "- Key files from prior pass: apex_compact_pages_pack.py, apex-tokens.css, "
        "apex-core.js, apex_backend.py widget builders, claims/HAL exemptions\n"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 10000,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Zero Scroll Widgets Consult"
    import urllib.request

    req = urllib.request.Request(
        base_url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            content = extract_message_content(json.loads(resp.read().decode()))
        status = "ok"
    except Exception as exc:
        content = str(exc)
        status = "error"
    header = (
        f"# Moonshot AI — Zero-Scroll Widgets Fix + Organize (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n**Model:** {model}  \n**Key:** {key_name}  \n"
        f"**Status:** {status}  \n**Build:** hal-10560  \n"
        f"**Script:** `scripts/run_moonshot_zero_scroll_widgets_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out = OUT / f"MOONSHOT_ZERO_SCROLL_WIDGETS_CONSULT_{DATE}.md"
    doc = DOCS / f"MOONSHOT_ZERO_SCROLL_WIDGETS_CONSULT_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    print(out)
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
