"""Moonshot AI — What's next after DEF-001 period-sync honesty (hal-10565).

Operator pattern: "next" → Moonshot consult; do not apply code.
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

OPERATOR_REQUEST_VERBATIM = "next"

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL
(hal-10565 + Phase 5 190Q GO + DEF-001 Collections honesty +
hal-local:32b / qwen3:32b Q4_K_M on R9700).

Operator said "next" — produce the SINGLE best next local work package.
CONSULT ONLY — DO NOT claim you applied code.
Prefer additive Apex/HAL/data fixes. Avoid GitHub/PR as the primary package.
Do not invent fictional file trees — only real paths listed below.

JUST SHIPPED (hal-10565 period sync ingestion — b018d0d):
- ingest_daysheet_to_period() + summarize/detect daysheet/register exports
- refresh_softdent_period_imports force_reimport when inbox matches
- Gap codes DAYSHEET_WITHOUT_SPLIT / COLLECTIONS_EXPORT_REQUIRED
- Register_for_period* inbox name match; quoted CSV money parse
- Live: 2026-07 still collectionsPending (production ~$45.6k);
  inbox classifiedPeriods include 2026-05/2026-06, coversOpenMonth=false;
  June register present with Ins Plan $0 → format/export required;
  July still needs Collections/Register MTD with real Ins/Patient split

JUST SHIPPED PRIOR:
- Period-sync honesty ebfad88 (COLLECTIONS_FORMAT_REQUIRED, no invent dumps)
- DEF-001 honesty gates hal-10564 (c645460)
- Phase 5 190Q GO (7e46a70)

OPS STILL OPEN (not a code package unless clearly highest ROI):
- SoftDent Register for a Period / Collections with Ins-Patient split
  for 2026-07 → C:\\SoftDentReportExports → Sync / Refresh SoftDent period
- Restart Start Program for hal-10565 IDB gate

OTHER OPEN (pick only if clearly higher ROI than the best local code
package OR an explicit OPS handoff):
- SoftDent SQLite lock residual (WHY-ERRORS timeout shipped)
- Browser smoke of density/cache/DEF-001 after hard-refresh
- Parse RegisterForPeriodReportFor07012026.xls (July XLS already in inbox)
  only if clearly higher ROI than OPS CSV export
- Any HAL latency / read-only polish not covered by Phase 5 GO

Do NOT redo: DEF-001 honesty gates, period-sync ingestion/format required,
invent SoftDentImportParser fiction, invent SoftDent write-back,
invent dollars, Phase 1–5 190Q, KPI density, cache coherence,
WHY-ERRORS timeout, CARC Phase 4.
Do not invent SoftDent write-back / dollars. empty ≠ $0.
Do NOT recommend inventing a greenfield CSV parser when OPS export
is the real blocker for live July dollars.

REAL PATHS:
- NewRidgeFinancial2/softdent_dashboard_period_sync.py
- NewRidgeFinancial2/apex_softdent_hardening_pack.py
- NewRidgeFinancial2/apex_financial_console_pack.py
- NewRidgeFinancial2/apex_backend.py
- NewRidgeFinancial2/softdent_practice_exports.py
- NewRidgeFinancial2/nr2_hal_gateway.py
- NewRidgeFinancial2/site/apex-core.js
- C:\\SoftDentReportExports
- NewRidgeFinancial2/docs/MOONSHOT_DEF001_PERIOD_SYNC_INGEST_APPLIED_2026-07-12.md
- NewRidgeFinancial2/docs/MOONSHOT_HAL_190Q_PHASE5_REPORT_2026-07-12.md

OUTPUT (strict markdown):
# Verdict (one sentence — THE next package)
## 0. Operator Intent (verbatim: next)
## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
## 2. Runner-ups (2–3, why not now)
## 3. What NOT to redo
## 4. Acceptance criteria
## 5. Executive Summary (5 bullets)
## 6. Approval checklist
DO NOT APPLY CODE. Prefer one clear next over a laundry list.
If the best next is OPS-only, say so clearly with exact SoftDent export steps.
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
        ("MOONSHOT_DEF001_PERIOD_SYNC_INGEST_APPLIED_2026-07-12.md", 2200),
        ("MOONSHOT_WHATS_NEXT_AFTER_DEF001_SHIPPED_2026-07-12.md", 1600),
        ("MOONSHOT_COLLECTIONS_DAYSHEET_APPLIED_2026-07-12.md", 1400),
        ("MOONSHOT_HAL_190Q_PHASE5_REPORT_2026-07-12.md", 1200),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = ""
    try:
        sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))
        from apex_softdent_hardening_pack import assess_collections_gap  # noqa: E402
        from apex_backend import _load_reports_and_bundle  # noqa: E402
        from import_loader import softdent_import_dir  # noqa: E402

        _reports, bundle, _err = _load_reports_and_bundle()
        gap = assess_collections_gap(bundle)
        dash_path = softdent_import_dir() / "softdent_dashboard_data.json"
        rows = []
        if dash_path.is_file():
            rows = json.loads(dash_path.read_text(encoding="utf-8-sig"))
        live = json.dumps(
            {
                "buildHint": "hal-10565 + b018d0d ingest",
                "gap": {
                    "gapCode": gap.get("gapCode"),
                    "collectionsGapCode": gap.get("collectionsGapCode"),
                    "healthy": gap.get("healthy"),
                    "period": gap.get("period"),
                    "collectionsPending": gap.get("collectionsPending"),
                    "collectionsFormatRequired": gap.get("collectionsFormatRequired"),
                    "daysheetWithoutSplit": gap.get("daysheetWithoutSplit"),
                    "collectionsExportRequired": gap.get("collectionsExportRequired"),
                    "production": gap.get("production"),
                    "exportInbox": {
                        "matchCount": (gap.get("exportInbox") or {}).get("matchCount"),
                        "classifiedPeriods": (gap.get("exportInbox") or {}).get(
                            "classifiedPeriods"
                        ),
                        "coversOpenMonth": (gap.get("exportInbox") or {}).get(
                            "coversOpenMonth"
                        ),
                        "matches": [
                            m.get("name")
                            for m in ((gap.get("exportInbox") or {}).get("matches") or [])[:8]
                        ],
                    },
                },
                "dashboardRows": [
                    {
                        "period": r.get("period"),
                        "production": r.get("production"),
                        "collections": r.get("collections"),
                        "collectionsPending": r.get("collectionsPending"),
                        "collectionsFormatRequired": r.get("collectionsFormatRequired"),
                        "insurance": r.get("insurance"),
                        "patient": r.get("patient"),
                    }
                    for r in (rows or [])
                    if isinstance(r, dict)
                ][:6],
                "uncommittedPracticeExports": (
                    REPO / "NewRidgeFinancial2" / "softdent_practice_exports.py"
                ).is_file(),
            },
            indent=2,
        )[:4500]
    except Exception as exc:  # noqa: BLE001
        live = f"(live snapshot failed: {exc})"

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "hal-10565 period sync ingestion JUST SHIPPED (b018d0d). "
        "Phase 5 190Q is GO. Pick THE next package. CONSULT ONLY.\n\n"
        f"## LIVE SNAPSHOT\n{live}\n\n"
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
        headers["X-Title"] = "NR2 Whats Next After Period Sync 10565"
    import urllib.request

    print("Calling Moonshot AI (consult only — will not apply)...")
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
        f"# Moonshot AI — What's Next After Period Sync Honesty (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** hal-10565 + Phase 5 GO  \n"
        f"**Prior:** period sync ingestion (`b018d0d`); format honesty (`ebfad88`); "
        f"DEF-001 (`c645460`); Phase 5 GO  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_period_sync_10565_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_PERIOD_SYNC_10565_{DATE}.md"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_PERIOD_SYNC_10565_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    print(out)
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
