"""Moonshot AI — Comprehensive SoftDent data ingestion for HAL reports.

CONSULT ONLY. Operator asked about ingesting ALL SoftDent data so HAL can
give a comprehensive report.
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
    "ask moonshot ai about a comprehensive ingestion of all data from softdent "
    "so that HAL can give a comprehensive report"
)

SYSTEM = """You are Moonshot AI — principal architect for NR2 Apex HAL + SoftDent.

CONSULT ONLY — DO NOT claim you applied code. DO NOT invent SoftDent write-back.
empty != $0. Period-close dollars = desktop SoftDent Excel exports
(C:\\SoftDentReportExports), NOT ODBC/sd_* as primary truth.
Never invent Ins Plan dollars; July Register Ins Plan $0 is SoftDent truth → ERA-835.
Do not recommend "ingest everything via ODBC overnight" as the primary plan.

Operator wants a COMPREHENSIVE SoftDent ingestion strategy so HAL can produce a
COMPREHENSIVE practice report. Design a phased program that:
1) Maps what is ALREADY live (use REAL paths below)
2) Names the MINIMUM additional domains needed for a "comprehensive HAL report"
3) Separates PERIOD-CLOSE $ (desktop Excel) vs OPS DETAIL (ODBC/sd_*) vs ERA insurance
4) Picks the SINGLE highest-leverage NEXT package (CODE or OPS) toward that goal
5) Lists what NOT to do (boiling the ocean, synthetic data, Register re-export for Ins Plan)

EXISTING (REAL — treat as shipped / live):
- Register for a Period Excel → production/collections/Ins Plan/Regular
  (softdent_practice_exports.py, softdent_dashboard_period_sync.py)
- Daysheet / Collections Summary Excel + JSONL
- Account transactions Excel year-chunks → sd_account_transactions (~549k rows)
  + HAL ledger policy + coverage chip
- ODBC sd_*: patients, appointments, procedures, claims, payments, adjustments,
  patient_insurance, carrier_payer_map (softdent_odbc_extract.py) — OPS detail lane
- Practice inbox datasets under app_data/nr2/document_inbox/softdent
- ERA-835 scaffold + discovery (often empty; ERA_835_REQUIRED)
- HAL policies: account-tx ledger, collections gap DEF-001, forbid Register re-export,
  ERA discover/inbox, SoftDent sign-on playbook
- GUI export kit / master reports catalog (softdent_master_reports.json)
- Phase-2 RESERVED (catalog only, not wired): production_by_provider report export,
  production_by_ada_code, collection_reconciliation, deposit_slip,
  outstanding_claims_by_co

BLOCKERS (REAL):
- ERA-835 local discovery often 0 — insurance collections detail blocked on procurement
- Daysheet-derived claims lack payer without sd_claims / claims export join
- Period $ must stay desktop Excel truth

REAL PATHS:
- C:\\SoftDentReportExports
- C:\\SoftDentFinancialExports
- C:\\SoftDentFinancialExports\\softdent_financial_analytics.db
- app_data/nr2/document_inbox/softdent/
- NewRidgeFinancial2/softdent_practice_exports.py
- NewRidgeFinancial2/softdent_dashboard_period_sync.py
- NewRidgeFinancial2/softdent_transaction_extract.py
- NewRidgeFinancial2/softdent_odbc_extract.py
- NewRidgeFinancial2/softdent_master_reports.json
- NewRidgeFinancial2/nr2_hal_gateway.py
- NewRidgeFinancial2/apex_softdent_hardening_pack.py
- NewRidgeFinancial2/apex_era835_pack.py
- NewRidgeFinancial2/docs/SOFTDENT_WIDGET_DATA_PATHS_2026-07-12.md
- NewRidgeFinancial2/docs/MOONSHOT_PRODUCTION_MAX_MERGE_HONESTY_HAL10579_APPLIED_2026-07-13.md
- NewRidgeFinancial2/docs/MOONSHOT_REGULAR_COLLECTIONS_DEF001_APPLIED_2026-07-13.md
- NewRidgeFinancial2/docs/MOONSHOT_ACCOUNT_TX_COVERAGE_CHIP_APPLIED_2026-07-13.md

OUTPUT (strict markdown):
# Verdict (one sentence — strategic answer + THE next package)
## 0. Operator Intent (verbatim)
## 1. Can HAL already give a "comprehensive" SoftDent report? (honest yes/partial/no + why)
## 2. Target architecture for comprehensive SoftDent → HAL report
   (layers: period-close $, ops detail, insurance ERA, clinical/schedule)
## 3. Gap matrix (domain | status live/partial/missing | source lane | HAL report use)
## 4. Recommended NEXT package toward comprehensive reporting
   (name, why now, effort, REAL files, validation gate)
## 5. Phased roadmap (3–5 phases; each with exit criteria)
## 6. What NOT to do
## 7. Executive Summary (5 bullets)
## 8. Approval checklist
Prefer one clear next package; do not laundry-list undifferentiated "ingest all tables".
"""


def _live_snapshot() -> str:
    live: dict = {}
    try:
        sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))
        from apex_backend import BUILD_ID  # noqa: E402
        from apex_softdent_hardening_pack import (  # noqa: E402
            assess_collections_gap,
            collections_gap_widget,
        )
        from apex_backend import _load_reports_and_bundle  # noqa: E402

        live["buildId"] = BUILD_ID
        _r, bundle, _e = _load_reports_and_bundle()
        gap = assess_collections_gap(bundle)
        live["gap"] = {
            k: gap.get(k)
            for k in (
                "period",
                "production",
                "collections",
                "patient",
                "regularCollections",
                "insurance",
                "collectionsGapCode",
                "suggestedAction",
                "registerInsPlanZero",
            )
        }
        live["widgetMessage"] = (collections_gap_widget(bundle) or {}).get("message")

        dash = (
            REPO
            / "app_data"
            / "nr2"
            / "document_inbox"
            / "softdent"
            / "softdent_dashboard_data.json"
        )
        if dash.is_file():
            rows = json.loads(dash.read_text(encoding="utf-8-sig"))
            live["dashboardPeriods"] = [
                {
                    "period": r.get("period"),
                    "production": r.get("production"),
                    "collections": r.get("collections"),
                    "patient": r.get("patient"),
                    "registerInsPlanZero": r.get("registerInsPlanZero"),
                }
                for r in rows
                if isinstance(r, dict)
            ][:6]

        # Account-tx coverage if available
        try:
            from softdent_transaction_extract import account_tx_coverage_summary  # type: ignore

            live["accountTxCoverage"] = account_tx_coverage_summary()
        except Exception:
            try:
                import sqlite3

                # Heuristic: find sd_account_transactions count if DB path helper exists
                from softdent_transaction_extract import resolve_account_transactions_db  # type: ignore

                db = resolve_account_transactions_db()
                if db and Path(db).is_file():
                    con = sqlite3.connect(str(db))
                    n = con.execute(
                        "SELECT COUNT(*) FROM sd_account_transactions"
                    ).fetchone()[0]
                    con.close()
                    live["accountTxRows"] = n
            except Exception as exc:  # noqa: BLE001
                live["accountTxNote"] = f"{type(exc).__name__}:{exc}"

        try:
            from apex_era835_pack import discover_era_candidates, scan_era_inbox

            live["eraInbox"] = {
                k: scan_era_inbox(ensure_dirs=True).get(k)
                for k in ("empty", "fileCount", "chipLabel")
            }
            disc = discover_era_candidates(limit=10, max_depth=3)
            live["eraDiscovery"] = {
                k: disc.get(k) for k in ("candidateCount", "chipLabel")
            }
        except Exception as exc:  # noqa: BLE001
            live["eraError"] = f"{type(exc).__name__}:{exc}"

        master = REPO / "NewRidgeFinancial2" / "softdent_master_reports.json"
        if master.is_file():
            mj = json.loads(master.read_text(encoding="utf-8"))
            live["masterReportsKeys"] = list(mj.keys())[:20]
            if isinstance(mj.get("phase2_reserved"), list):
                live["phase2Reserved"] = mj.get("phase2_reserved")[:12]
            elif isinstance(mj.get("phase2_reserved"), dict):
                live["phase2Reserved"] = list(mj.get("phase2_reserved").keys())[:12]
    except Exception as exc:  # noqa: BLE001
        live["error"] = f"{type(exc).__name__}:{exc}"
    return json.dumps(live, indent=2, default=str)[:10000]


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
        ("SOFTDENT_WIDGET_DATA_PATHS_2026-07-12.md", 2800),
        ("MOONSHOT_PRODUCTION_MAX_MERGE_HONESTY_HAL10579_APPLIED_2026-07-13.md", 1600),
        ("MOONSHOT_REGULAR_COLLECTIONS_DEF001_APPLIED_2026-07-13.md", 1600),
        ("MOONSHOT_ACCOUNT_TX_COVERAGE_CHIP_APPLIED_2026-07-13.md", 1400),
        ("MOONSHOT_ERA_REMITTANCE_DISCOVERY_APPLIED_2026-07-12.md", 1200),
        ("MOONSHOT_SOFTDENT_INSURANCE_EXTRACT_APPLIED_2026-07-11.md", 1400),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Design a comprehensive SoftDent ingestion strategy so HAL can produce a "
        "comprehensive practice report. Be honest about what is already live vs missing. "
        "Pick ONE next package. CONSULT ONLY — do not apply.\n\n"
        f"## LIVE SNAPSHOT\n{live}\n\n"
        + "\n\n".join(excerpts)
    )
    payload = {
        "model": model,
        "temperature": 1.0,
        "max_tokens": 9000,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 SoftDent Comprehensive Ingest for HAL Report"
    print("Calling Moonshot AI (consult only — will not apply)...")

    req_data = json.dumps(payload).encode()
    import urllib.request

    req = urllib.request.Request(base_url, data=req_data, headers=headers, method="POST")
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
    (OUT / f"moonshot_softdent_comprehensive_ingest_hal_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10576"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — Comprehensive SoftDent Ingestion for HAL Reports (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** Production max-merge honesty (`15099e8` / hal-10579)  \n"
        f"**Script:** `scripts/run_moonshot_softdent_comprehensive_ingest_hal_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)").strip() + "\n"
    doc = DOCS / f"MOONSHOT_SOFTDENT_COMPREHENSIVE_INGEST_HAL_{DATE}.md"
    out = OUT / f"MOONSHOT_SOFTDENT_COMPREHENSIVE_INGEST_HAL_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    sys.stdout.buffer.write(((content or "")[:6000] + "\n").encode("utf-8", errors="replace"))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
