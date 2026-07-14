"""Moonshot AI — Fix-all issues from post-restart page inspect (CONSULT ONLY).

Operator: send the active/faulty page inspect report for consult on how to
fix all remaining issues, then report. Do NOT apply code until approved.
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
    "send to moonshot the report for consult on how to fix all the issues and report"
)

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL (hal-10608).

OPERATOR INTENT: Consult on HOW TO FIX ALL remaining issues from the live
page-inspect report. CONSULT ONLY — do not claim you applied code.
If concrete code patches help non-OPS items, INCLUDE full unified diffs.
Never invent SoftDent Gold CSV / ERA dollars / Print Preview → Gold.

ALREADY APPLIED (do NOT redo; treat as done):
- Widget `/api/apex/widgets*` + `/api/apex/hal/orchestrate` rate-limit exempt
- apex-core.js exponential warming backoff + buildId skew reload
- Warming stub Cache-Control no-store + X-NR2-Build-Id
- Chrome ASSET_V / index.html / sw.js aligned to hal-10608
- Doc: MOONSHOT_APPLIED_PAGE_SMOKE_ANALYZE_REPAIRS_2026-07-13.md
- Commit: 4aca8b2 on fix/main-validate-ci

POST-RESTART LIVE INSPECT (after those fixes):
- Health OK · ollama OK · mosaic buildId=hal-10608 · warm ~8s · 0 crashed
- 177 widgets: 139 ACTIVE · 38 FAULTY/empty/gap · 11/11 pages navigate
- SoftDent A/R dataset STALE (~18h / 1104 min; max 120) — critical import gap
- app-info schemaVersion may still say hal-10576 while widgets buildId is
  hal-10608 (note if residual skew remains in app-info only)

PAGE ACTIVE/FAULT:
financial 35 (32/3), taxes 9 (8/1), softdent 31 (24/7), quickbooks 9 (9/0),
ar 13 (11/2), claims 18 (12/6), narratives 5 (3/2), documents 5 (4/1),
library 3 (1/2), office-manager 34 (22/12), hal 15 (13/2)

FAULTY LIST (fix ALL — group into packages):
CRITICAL OPS/HONESTY:
- softdent-gold-payment-pipeline / softdent-gold-csv-drop-ops: GOLD_CSV_MISSING
- softdent-print-preview-audit / softdent-visual-ledger-recon: GOLD_CSV_MISSING
  (visual $641,566.92 — NOT gold; do not invent)
- softdent-collections-gap: ERA_835_REQUIRED
- softdent-outstanding-claims-bridge: CLAIMS_AR_RECONCILE_MISMATCH claims=61
- claims/om import-health-monitor: DEF-001 ERA_835_REQUIRED
- claims/om ins-patient-split: ERA_835_REQUIRED
- claims-era-gauge: empty

EMPTY MODULES (may be code wire OR missing data):
- financial: procedure-profitability-scatter, treatment-conversion-pipeline,
  cash-flow-bridge
- taxes: c0-import-guidance (2/3 OK)
- ar: ar-forecast-trend, unapplied-credit-float
- claims: denial-pareto, preauth-aging-lanes, verification-matrix
- narratives: narr-workflow, kpi-data-pending
- documents: tax-returns-library
- library: lib-storage (Not indexed), kpi-data-pending
- office-manager: payer-change-alerts, recall-gauge,
  treatment-conversion-pipeline, verification-matrix, patient-dossier-card,
  eligibility-card, patient-dossier-mini, active-treatment-plans,
  claim-review-detail, clinical-notes-summary (+ ERA widgets above)
- softdent: softdent-patient-dossier
- hal: payer-change-alerts, hal-recommended-actions

YOUR JOB:
1) Produce a COMPLETE fix plan covering ALL 38 faulties — every id must map
   to OPS step, CODE package, or WONTFIX/honest-empty with reason.
2) Rank MUST → SHOULD → OPS → NICE. Prefer practice-truth unblockers first
   (Gold CSV procurement, ERA 835, SoftDent A/R refresh).
3) For CODE packages: real file paths + unified diffs when justified.
4) For OPS: exact SoftDent/Carestream/export steps; no invented dollars.
5) Do not redo the already-applied 429/warming patches.

REAL PATHS (examples):
- NewRidgeFinancial2/apex_backend.py
- NewRidgeFinancial2/softdent_gold_csv_drop_ops.py
- NewRidgeFinancial2/softdent_gold_era_settlement_hal10608.py
- NewRidgeFinancial2/softdent_treatment_planning.py
- NewRidgeFinancial2/docs/CARESTREAM_SUPPORT_TICKET_GOLD_CSV_2026-07-13.md
- NewRidgeFinancial2/docs/MOONSHOT_APPLIED_PAGE_SMOKE_ANALYZE_REPAIRS_2026-07-13.md
- NewRidgeFinancial2/docs/_nr2_page_inspect_report.json
- C:\\SoftDentReportExports · C:\\SoftDentFinancialExports

OUTPUT (strict markdown):
# Verdict (one sentence)
## 0. Operator Intent (verbatim; consult-only)
## 1. Issue Map — all 38 faulties → OPS / CODE / HONEST-EMPTY
## 2. Recommended Fix Program (MUST / SHOULD / OPS / NICE ranked)
## 3. Code Patches (if any) — full unified diffs
## 4. OPS Playbooks (Gold / ERA / SoftDent A/R stale) — exact steps
## 5. What NOT to invent / redo
## 6. Acceptance criteria (how we know ALL issues closed or honestly deferred)
## 7. Executive Summary (5–7 bullets)
## 8. Approval checklist
"""


def _faulty_table() -> str:
    p = DOCS / "_nr2_page_inspect_report.json"
    if not p.is_file():
        return "(inspect JSON missing)"
    data = json.loads(p.read_text(encoding="utf-8"))
    lines = [
        f"summary={data.get('summary')}",
        "pages:",
    ]
    for page, info in (data.get("pages") or {}).items():
        lines.append(f"  {page}: n={info.get('n')} by={info.get('by')} build={info.get('buildId')}")
    lines.append("faulty:")
    for g in data.get("faulty") or []:
        lines.append(
            f"  {g.get('page')}\t{g.get('id')}\t{g.get('status')}\t"
            f"{g.get('gapCode')}\t{(g.get('msg') or '')[:120]}"
        )
    lines.append("chrome_apis:")
    for path, info in (data.get("chrome_apis") or {}).items():
        lines.append(f"  {path} http={info.get('http')} ok={info.get('ok')} {info.get('snip','')[:100]}")
    return "\n".join(lines)


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

    applied = DOCS / "MOONSHOT_APPLIED_PAGE_SMOKE_ANALYZE_REPAIRS_2026-07-13.md"
    carestream = DOCS / "CARESTREAM_SUPPORT_TICKET_GOLD_CSV_2026-07-13.md"
    excerpts = []
    if applied.is_file():
        excerpts.append(f"--- APPLIED ---\n{applied.read_text(encoding='utf-8')[:2500]}")
    if carestream.is_file():
        excerpts.append(f"--- CARESTREAM TICKET ---\n{carestream.read_text(encoding='utf-8')[:2000]}")

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Consult on how to fix ALL remaining page-inspect issues. Report a full "
        "fix program. CONSULT ONLY. Include code diffs only where justified.\n\n"
        "## Live inspect report\n"
        f"{_faulty_table()}\n\n"
        + "\n\n".join(excerpts)
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 14000,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Fix-All Page Inspect Consult"
    import urllib.request

    print("Calling Moonshot AI (fix-all page inspect — consult only)...")
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

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    header = (
        f"# Moonshot AI — Fix-All Page Inspect Issues (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**UTC:** {stamp}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** hal-10608  \n"
        f"**Source inspect:** `docs/_nr2_page_inspect_report.json` (139 active / 38 faulty)  \n"
        f"**Prior applied:** page-smoke 429/warming repairs (`4aca8b2`)  \n"
        f"**Script:** `scripts/run_moonshot_fix_all_page_inspect_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out = OUT / f"moonshot_fix_all_page_inspect_{stamp}.md"
    doc = DOCS / f"MOONSHOT_FIX_ALL_PAGE_INSPECT_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    (OUT / f"moonshot_fix_all_page_inspect_{stamp}.json").write_text(
        json.dumps(
            {
                "status": status,
                "model": model,
                "operator": OPERATOR_REQUEST_VERBATIM,
                "chars": len(content or ""),
                "doc": str(doc),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(out)
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
