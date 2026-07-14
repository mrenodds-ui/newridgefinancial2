"""Moonshot AI — What's next after DEF-001 Collections/Daysheet (hal-10564).

Operator said "proceed" — consult first, then apply THE recommended package
in the same turn once the consult lands (operator approval already given).
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
(hal-10564 + Phase 5 190Q GO + DEF-001 Collections honesty +
hal-local:32b / qwen3:32b Q4_K_M on R9700).

Operator said "proceed" after DEF-001 Collections/Daysheet (hal-10564)
was applied and pushed (c645460). Produce the SINGLE best next local
work package. Prefer additive Apex/HAL/data fixes. Avoid GitHub/PR as
the primary package. Do not invent fictional file trees — only real
paths listed below.

JUST SHIPPED (hal-10564 — c645460):
- DEF-001: scan_collections_export_inbox, period-aware empty
  revenue-composition, Financial gap strip, HAL local policy
  policy:def-001-collections, refresh SoftDent period inbox scan
- Honesty: empty ≠ $0; no invented insurance/patient dollars
- Docs: MOONSHOT_COLLECTIONS_DAYSHEET_AFTER_PHASE5 /
  MOONSHOT_COLLECTIONS_DAYSHEET_APPLIED
- Ops STILL OPEN: SoftDent Collections/Daysheet CSV for 2026-07 into
  C:\\SoftDentReportExports + Sync to populate live split (code honesty
  gates are done; live dollars need staff export)

JUST SHIPPED PRIOR:
- Phase 5 190Q GO: 190/190 success, quality 98.9%, read-only 100%,
  avg 13.6s, empty fails 0 (7e46a70)
- Cache coherence hal-10563; KPI density hal-10562

OTHER OPEN (pick only if clearly higher ROI than ops-close DEF-001
or the next highest-impact local package):
- SoftDent SQLite lock residual (WHY-ERRORS connect timeout shipped)
- Browser smoke of density/cache/DEF-001 after hard-refresh
- SoftDent daysheet→dashboard period sync if inbox has daysheet files
  but collectionsPending remains
- Any remaining HAL latency / read-only polish not covered by Phase 5 GO

Do NOT redo: DEF-001 honesty gates, invent Collections CSV parsers with
fake schemas, invent SoftDent write-back, invent dollars, Phase 1–5
190Q, KPI density, cache coherence, WHY-ERRORS timeout, CARC Phase 4.
Do not invent SoftDent write-back / dollars. empty ≠ $0.

REAL PATHS:
- NewRidgeFinancial2/apex_softdent_hardening_pack.py
- NewRidgeFinancial2/apex_financial_console_pack.py
- NewRidgeFinancial2/apex_backend.py (refresh_softdent_period_imports)
- NewRidgeFinancial2/softdent_dashboard_period_sync.py
- NewRidgeFinancial2/softdent_practice_exports.py
- NewRidgeFinancial2/nr2_hal_gateway.py
- NewRidgeFinancial2/site/apex-core.js, site/indexeddb-store.js
- C:\\SoftDentReportExports (ops inbox)
- NewRidgeFinancial2/docs/MOONSHOT_COLLECTIONS_DAYSHEET_APPLIED_2026-07-12.md
- NewRidgeFinancial2/docs/MOONSHOT_HAL_190Q_PHASE5_REPORT_2026-07-12.md

OUTPUT (strict markdown):
# Verdict (one sentence — THE next package)
## 0. Operator Intent (verbatim: proceed)
## 1. Recommended NEXT (name, why now, effort, REAL files, phases, validation gate)
## 2. Runner-ups (2–3, why not now)
## 3. What NOT to redo
## 4. Acceptance criteria
## 5. Executive Summary (5 bullets)
## 6. Approval checklist (operator already said proceed — list apply steps)
Prefer one clear next over a laundry list. If the best next is OPS-only
(staff SoftDent export), say so clearly and give exact checklist — do not
invent a greenfield parser package.
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
        ("MOONSHOT_COLLECTIONS_DAYSHEET_APPLIED_2026-07-12.md", 2200),
        ("MOONSHOT_COLLECTIONS_DAYSHEET_AFTER_PHASE5_2026-07-12.md", 1800),
        ("MOONSHOT_HAL_190Q_PHASE5_REPORT_2026-07-12.md", 1600),
        ("MOONSHOT_WHATS_NEXT_AFTER_CACHE_COHERENCE_2026-07-12.md", 1400),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    # Live inbox / gap snapshot for grounded consult
    live = ""
    try:
        sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))
        from apex_softdent_hardening_pack import (  # noqa: E402
            assess_collections_gap,
            scan_collections_export_inbox,
        )

        inbox = scan_collections_export_inbox(limit=8)
        gap = assess_collections_gap(None)
        live = json.dumps(
            {
                "exportInbox": {
                    "matchCount": inbox.get("matchCount"),
                    "matches": inbox.get("matches"),
                    "hint": inbox.get("hint"),
                    "roots": inbox.get("roots"),
                },
                "gap": {
                    "gapCode": gap.get("gapCode"),
                    "collectionsGapCode": gap.get("collectionsGapCode"),
                    "healthy": gap.get("healthy"),
                    "period": gap.get("period"),
                    "collectionsPending": gap.get("collectionsPending"),
                    "fixHint": gap.get("fixHint"),
                },
            },
            indent=2,
        )[:4000]
    except Exception as exc:  # noqa: BLE001
        live = f"(live snapshot failed: {exc})"

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "DEF-001 Collections honesty JUST SHIPPED (hal-10564 / c645460). "
        "Phase 5 190Q is GO. Pick THE next package. Operator already said "
        "proceed — recommend the apply target.\n\n"
        f"## LIVE DEF-001 SNAPSHOT\n{live}\n\n"
        + "\n\n".join(excerpts)
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
        headers["X-Title"] = "NR2 Whats Next After DEF-001"
    import urllib.request

    print("Calling Moonshot AI (what's next after DEF-001)...")
    req = urllib.request.Request(
        base_url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            content = extract_message_content(json.loads(resp.read().decode()))
        status = "ok"
    except Exception as exc:  # noqa: BLE001
        content = str(exc)
        status = "error"

    header = (
        f"# Moonshot AI — What's Next After DEF-001 Collections (CONSULT)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** hal-10564 + Phase 5 GO  \n"
        f"**Prior:** DEF-001 (`c645460`); Phase 5 GO (`7e46a70`)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_def001_consult.py`  \n"
        f"**Apply:** Operator already said proceed — apply THE recommended package after this consult lands.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_DEF001_{DATE}.md"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_DEF001_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    print(out)
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
