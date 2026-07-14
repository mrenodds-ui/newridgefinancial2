"""Moonshot AI — What's next after Phase 5 GO: Collections/Daysheet (CONSULT ONLY).

Operator said proceed after Phase 5 GO — prior consults queued Collections/Daysheet.
This script asks Moonshot for THE concrete fix package. Do not apply in this script.
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

OPERATOR_REQUEST_VERBATIM = "proceed"

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL
(hal-10563 + Phase 5 GO + hal-local:32b).

Operator said "proceed" AFTER Phase 5 190Q GO. Prior what's-next docs queued
**Collections/Daysheet export gap → empty revenue-composition** as the next
data package once Phase 5 passed.

CONSULT ONLY in this step — prescribe THE single fix package (ops + code).
Do not invent SoftDent write-back or dollar amounts. empty ≠ $0.

JUST SHIPPED:
- Phase 5 GO: 190/190, quality 98.9%, read-only 100%, avg 13.6s, empty 0
  (MOONSHOT_HAL_190Q_PHASE5_REPORT / FIX_PHASE5_APPLIED)
- KPI density hal-10562; cache coherence hal-10563

KNOWN GAP (DEF-001 from MOONSHOT_WHATS_WRONG):
- revenue-composition empty; collectionsPending on SoftDent latest period
- Needs SoftDent Collections/Daysheet (or Register-for-period) export into
  SoftDentReportExports / document inbox — then Sync
- Honesty: pending collections stay empty, never $0

Prescribe ONE package that:
1. Clarifies ops export path + period
2. Improves code if imports exist but are missed (parsers, dataset keys,
   playbook widgets, HAL sync hints)
3. Validates revenue-composition / vitals populate OR stay honestly empty
   with actionable hint

REAL PATHS (use only these families):
- NewRidgeFinancial2/apex_financial_console_pack.py (revenue-composition)
- NewRidgeFinancial2/apex_backend.py, apex_softdent_* packs
- SoftDent export / import pipeline: softdent_practice_exports.py,
  practice_source_access.py, import_direct_pipeline.py, import_loader
- Docs: MOONSHOT_WHATS_WRONG_*, IMPORT_HEALTH_*, PLAYBOOK if present

OUTPUT (strict markdown):
# Verdict
## 0. Operator Intent (proceed after Phase 5 GO)
## 1. Recommended NEXT package (name, why now, effort, REAL files, phases)
## 2. Ops checklist (exact export steps)
## 3. Code changes (if any) with validation gate
## 4. What NOT to do
## 5. Acceptance criteria
## 6. Approval checklist
DO NOT APPLY CODE in this consult output — prescription only.
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

    excerpts = []
    for name, lim in (
        ("MOONSHOT_HAL_190Q_PHASE5_REPORT_2026-07-12.md", 1500),
        ("MOONSHOT_WHATS_NEXT_AFTER_CACHE_COHERENCE_2026-07-12.md", 2000),
        ("MOONSHOT_WHATS_WRONG_CONSULT_2026-07-10.md", 2200),
        ("MOONSHOT_WHATS_WRONG_APPLIED_2026-07-10.md", 1200),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Phase 5 GO complete. Operator proceeds to queued Collections/Daysheet "
        "package. Prescribe THE concrete package (ops + optional code). "
        "CONSULT ONLY.\n\n" + "\n\n".join(excerpts)
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 7000,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Collections Daysheet After Phase5"
    import urllib.request

    print("Calling Moonshot AI (consult)...")
    req = urllib.request.Request(
        base_url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            content = extract_message_content(json.loads(resp.read().decode()))
        status = "ok"
    except Exception as exc:
        content = str(exc)
        status = "error"

    header = (
        f"# Moonshot AI — Collections/Daysheet After Phase 5 GO (CONSULT)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** hal-10563 + Phase 5 GO  \n"
        f"**Script:** `scripts/run_moonshot_collections_daysheet_after_phase5_consult.py`  \n"
        f"**Apply:** Operator already said proceed — apply after this consult lands.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out = OUT / f"MOONSHOT_COLLECTIONS_DAYSHEET_AFTER_PHASE5_{DATE}.md"
    doc = DOCS / f"MOONSHOT_COLLECTIONS_DAYSHEET_AFTER_PHASE5_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    print(out)
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
