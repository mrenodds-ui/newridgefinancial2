"""Moonshot AI — What's next after HAL-10589 gold Print Preview OPS (CONSULT ONLY).

Operator said: next
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
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

OPERATOR_REQUEST_VERBATIM = "next"

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL + SoftDent RCM.

Operator said NEXT after HAL-10589 just shipped on fix/main-validate-ci (cfdb92a).

CONSULT ONLY — DO NOT claim you applied code. empty != $0.
No SoftDent write-back. Do not invent Ins Plan Register dollars or carrier names.
Do NOT redo HAL-10580–10589 as greenfield — build ON them.

JUST SHIPPED (HAL-10589 / OPS-10589 — SoftDent Gold CSV Drop Facilitation & Print Preview):
- softdent_gold_csv_drop_ops.py: playbook, schema verify, pre/post checklist, Sync hook,
  widget/API/HAL; BUILD_ID=hal-10589
- SoftDent v19.1.4 discovery: NO menu named "Insurance Payment Analysis"
- Closest menus: Insurance Income (primary), Contractual Plan Analysis,
  Payment Allocation, Insurance Payment Distribution
- Operator fact: Excel is NOT available for these reports → Print Preview ONLY
  (click Print Preview → Enter → Next/PageDown through pages → LAST page for totals).
  Page 1 alone is incomplete. Never Printer.
- navigate_softdent_print_preview_pages() pages forward then last-page totals
- Live still: sd_insurance_payment_lines=0, gapCode=GOLD_CSV_MISSING
- Print Preview does NOT produce gold CSV / does NOT populate payment lines
- Exact usable spine still 46/46 pass (consistency only; no remittance gold)
- Prior: HAL-10588 ETL ready; 10580–10587 InsCo×ADA spine/catalog/TP on ledger fallback

CRITICAL GROUND TRUTH: The gold CSV fantasy is blocked by SoftDent product reality
on this build (Print Preview only, no Insurance Payment Analysis CSV). Do NOT
recommend "drop the CSV" as if Excel exists. Prefer the next highest-leverage
package that accepts Print Preview / ledger truth OR unblocks a real alternative
data plane (ERA, etc.) without inventing dollars.

Pick THE single best NEXT package. Prefer additive local CODE/OPS. Avoid GitHub/PR primary.

OPEN CANDIDATES (pick ONE — argue from current blockers):
1) CODE: SoftDent Print Preview visual-capture / last+next-page audit protocol —
   structured note of Insurance Income totals (PHI-safe aggregates only), honesty
   that this is NOT gold line ingest; empty != $0
2) CODE: Empty≠$0 programmatic UI enforcement audit (HON-001) — prove no null
   renders as $0.00 across Apex/SoftDent widgets while gold remains empty
3) CODE: Remittance/ERA835 first-drop cross-check vs 46 exact usable cells —
   only if real ERA files exist on disk; do not invent
4) CODE: Catalog/spine reliability without gold — secondary-ins exclusion,
   same-day settlement, borderline-n bootstrap (grow beyond 46 carefully)
5) OPS+CODE: Uncovered ledger CDT playbook (47 CDTs with no 2/51 pairing)
6) CODE: Async HAL / ASGI queue (ENH-001) — latency; not data-famine unblocking
7) CODE: Alternate SoftDent report evaluation (Contractual Plan Analysis /
   Payment Allocation Print Preview) — which preview has ADA×InsCo usable shape
   for staff visual RCM (still not inventing CSV)

What NOT to redo: SoftDent write-back; invent gold from ledger/DaySheet;
pretend Excel/CSV exists for Insurance Income; BUILD_ID drift; redo TP chips/
catalog/spine; Register re-export Ins Plan>0; GitHub/PR as primary next;
re-litigate HAL-10588/10589 discovery.

OUTPUT (strict markdown):
# Verdict (one sentence — THE next package)
## 0. Operator Intent (verbatim)
## 1. Recommended NEXT (name, why now, effort, REAL files/ops steps, validation gate)
## 2. Why this beats the other candidates now
## 3. Runner-ups (2–3, why not now)
## 4. What NOT to redo
## 5. Acceptance criteria
## 6. Executive Summary (5 bullets)
## 7. Approval checklist
DO NOT APPLY CODE. Prefer one clear next over a laundry list.
"""


def _live_snapshot() -> str:
    live: dict = {
        "prior": "cfdb92a HAL-10589 gold Print Preview OPS + page-through",
        "appliedDoc": "MOONSHOT_APPLIED_HAL10589_GOLD_CSV_DROP_OPS_2026-07-13.md",
        "consultDoc": "MOONSHOT_WHATS_NEXT_AFTER_HAL10588_2026-07-13.md",
        "operatorAsk": "next",
        "softdentReality": {
            "noInsurancePaymentAnalysisMenu": True,
            "excelAvailableForInsuranceIncome": False,
            "outputMode": "print_preview_only",
            "pageThroughRequired": True,
            "printPreviewDoesNotPopulateGoldLines": True,
        },
    }
    try:
        sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))
        from apex_backend import BUILD_ID  # noqa: E402
        from softdent_gold_csv_drop_ops import (  # noqa: E402
            PACKAGE_BUILD_ID,
            checklist_post_ingest,
            gold_csv_drop_playbook,
        )
        from softdent_gold_payment_pipeline import audit_gold_payment_pipeline  # noqa: E402
        from softdent_insco_ada_catalog_matrix import catalog_matrix_status  # noqa: E402

        live["buildId"] = BUILD_ID
        live["packageBuildId"] = PACKAGE_BUILD_ID
        live["buildIdCoupled"] = BUILD_ID == PACKAGE_BUILD_ID == "hal-10589"
        live["goldAudit"] = {
            k: audit_gold_payment_pipeline().get(k)
            for k in ("gapCode", "paymentLines", "treatmentEstimates", "rootCause")
        }
        live["opsPost"] = checklist_post_ingest()
        live["playbook"] = gold_csv_drop_playbook()
        live["catalog"] = {
            k: catalog_matrix_status().get(k)
            for k in (
                "ok",
                "totalCells",
                "exactUsableCells",
                "publishedCells",
                "insufficientCells",
                "ledgerCdtUniverse",
            )
        }
        exports = Path(r"C:\SoftDentFinancialExports")
        if exports.is_dir():
            live["insurancePaymentCsvSample"] = sorted(
                p.name for p in exports.glob("insurance_payment*")
            )[:10]
            live["eraLikeFilesSample"] = sorted(
                {
                    p.name
                    for pat in ("*835*", "*era*", "*ERA*", "*remit*")
                    for p in exports.glob(pat)
                }
            )[:20]
            live["printPreviewOpsNotes"] = sorted(
                p.name for p in exports.glob("gold_print_preview_ops*")
            )[:5]
        db = Path(r"C:\SoftDentFinancialExports\softdent_financial_analytics.db")
        if db.is_file():
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                for table, key in (
                    ("sd_insurance_payment_lines", "paymentLines"),
                    ("treatment_planning_estimates", "tpEstimates"),
                    ("era_835_payments", "era835"),
                ):
                    try:
                        live[key] = int(
                            con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0
                        )
                    except sqlite3.Error:
                        live[key] = None
            finally:
                con.close()
    except Exception as exc:  # noqa: BLE001
        live["error"] = f"{type(exc).__name__}:{exc}"
    return json.dumps(live, indent=2, default=str)[:16000]


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No API key", file=sys.stderr)
        return 1
    if "moonshot" in (base_url or "").lower():
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    else:
        model = str(
            os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2"
        ).strip()
    print(f"Using {key_name} @ {base_url} model={model}")

    excerpts = []
    for name, lim in (
        ("MOONSHOT_APPLIED_HAL10589_GOLD_CSV_DROP_OPS_2026-07-13.md", 3200),
        ("MOONSHOT_WHATS_NEXT_AFTER_HAL10588_2026-07-13.md", 2200),
        ("MOONSHOT_EXPERT_SE_FIRST_CLASS_PROGRAM_2026-07-13.md", 2000),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "HAL-10589 Print Preview OPS just shipped. SoftDent has no Insurance Payment "
        "Analysis CSV path (Excel unavailable). Pick THE next package. CONSULT ONLY.\n\n"
        f"## LIVE SNAPSHOT\n{live}\n\n"
        + "\n\n".join(excerpts)
    )
    payload = {
        "model": model,
        "temperature": 1.0,
        "max_tokens": 7000,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Whats Next After HAL-10589"
    print("Calling Moonshot AI (what's next after 10589 — consult only)...")

    req = urllib.request.Request(
        base_url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        content = extract_message_content(raw)
        status = "ok"
    except Exception as exc:  # noqa: BLE001
        content = str(exc)
        status = "error"
        raw = {"error": content}

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (OUT / f"moonshot_whats_next_after_hal10589_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10589"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — What's Next After HAL-10589 Gold Print Preview OPS "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** HAL-10589 gold Print Preview OPS (`cfdb92a`)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_hal10589_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves (`proceed`).\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_HAL10589_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_HAL10589_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(out)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
