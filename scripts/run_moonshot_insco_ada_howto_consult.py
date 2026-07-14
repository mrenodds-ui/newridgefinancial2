"""Moonshot AI — How to derive InsCo × ADA paid-after-write-off from ALL NR2 data.

CONSULT ONLY. Operator: ask moonshot how to extrapolate plan pays per ADA.
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

OPERATOR_REQUEST_VERBATIM = (
    "based on transactional history of all patients their insurance coverage, "
    "claims involved with each patient and the transactionsal history of each "
    "patients insurance write off an insurance payment can you extrapulate what "
    "each insurance plan pays for each ada code? ask moonshot ai with all the "
    "data how to do it"
)

SYSTEM = """You are Moonshot AI — principal SoftDent/RCM data architect for NR2 Apex HAL.

Operator wants a HOW-TO: extrapolate what each insurance plan pays for each ADA
code from ALL available patient transactional history, insurance coverage,
claims, insurance write-offs, and insurance payments.

CONSULT ONLY — DO NOT claim you applied code. Do not invent SoftDent write-back,
Ins Plan Register dollars, or fictional file paths. empty != $0.
Honesty: if a join is not traversable, say so and give the real unblock path.

You already designed (2026-07-10) Insurance Payment Analysis →
sd_insurance_payment_lines → treatment_planning_estimates (hal-10400 APPLIED).
That pipeline EXISTS but LIVE payment lines are still 0 — operator has not
exported the CSV yet. Ledger + coverage + claims alone cannot do the join.

TASK: With ALL current live data + the applied pipeline, produce a concrete
HOW-TO for the practice to get InsCo × ADA paid-after-write-off estimates into
HAL — ranked steps, SoftDent UI export recipe, validation gates, and what
NOT to attempt from the 549k ledger alone.

OUTPUT (strict markdown):
# Verdict (one sentence — the HOW)
## 0. Operator Intent (verbatim)
## 1. Can ledger+coverage+claims alone do it? (YES/NO + why, with live evidence)
## 2. Correct HOW-TO (ordered steps — SoftDent UI + NR2 files + sync + HAL check)
## 3. What each data source contributes (table → role → cannot do)
## 4. Extrapolation / statistics rules (sample_size, medians, secondary, deductible honesty)
## 5. Optional enrichments (ERA 835 SVC, fee schedules, Sensei) — when useful
## 6. What NOT to do
## 7. Acceptance criteria / validation gates
## 8. Executive Summary (5 bullets)
## 9. Approval checklist (operator actions only — export, drop files, sync)
Prefer concrete SoftDent menu paths and REAL repo paths from LIVE SNAPSHOT.
"""


def _count(con: sqlite3.Connection, sql: str) -> int:
    try:
        return int(con.execute(sql).fetchone()[0] or 0)
    except Exception:
        return -1


def _live_snapshot() -> str:
    live: dict = {
        "priorConsult": "MOONSHOT_SOFTDENT_ADA_PAYER_TX_CONSULT_2026-07-10.md → PARTIAL",
        "priorApply": "MOONSHOT_SOFTDENT_ADA_PAYER_TX_APPLIED_2026-07-10.md (hal-10400)",
        "payerAttribution": "HAL-10581 Sensei → sd_patient_insurance + named sd_claims (7da1531)",
        "pipelineModule": "NewRidgeFinancial2/softdent_treatment_planning.py",
        "exportRoot": r"C:\SoftDentFinancialExports",
        "mustExport": "SoftDent Reports → Insurance → Insurance Payment Analysis (~24 mo) → CSV",
        "optionalExport": "Procedure Code Listing → procedure_codes_*.csv",
        "dropAs": r"C:\SoftDentFinancialExports\insurance_payments_YYYYMMDD.csv",
    }
    try:
        sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))
        from apex_backend import BUILD_ID  # noqa: E402

        live["buildId"] = BUILD_ID
    except Exception as exc:  # noqa: BLE001
        live["buildIdError"] = f"{type(exc).__name__}:{exc}"

    db = Path(r"C:\SoftDentFinancialExports\softdent_financial_analytics.db")
    live["dbPath"] = str(db)
    live["dbExists"] = db.is_file()
    if db.is_file():
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            live["counts"] = {
                "sd_account_transactions": _count(con, "SELECT COUNT(*) FROM sd_account_transactions"),
                "sd_patient_insurance": _count(con, "SELECT COUNT(*) FROM sd_patient_insurance"),
                "sd_claims": _count(con, "SELECT COUNT(*) FROM sd_claims"),
                "sd_claims_named": _count(
                    con,
                    """
                    SELECT COUNT(*) FROM sd_claims
                    WHERE payer IS NOT NULL AND TRIM(payer) != ''
                      AND LOWER(TRIM(payer)) NOT IN ('insurance','unknown','n/a','-')
                    """,
                ),
                "sd_procedures": _count(con, "SELECT COUNT(*) FROM sd_procedures"),
                "sd_payments": _count(con, "SELECT COUNT(*) FROM sd_payments"),
                "sd_adjustments": _count(con, "SELECT COUNT(*) FROM sd_adjustments"),
                "sd_insurance_payment_lines": _count(
                    con, "SELECT COUNT(*) FROM sd_insurance_payment_lines"
                ),
                "treatment_planning_estimates": _count(
                    con, "SELECT COUNT(*) FROM treatment_planning_estimates"
                ),
                "sd_procedure_code_reference": _count(
                    con, "SELECT COUNT(*) FROM sd_procedure_code_reference"
                ),
                "fee_schedules": _count(con, "SELECT COUNT(*) FROM fee_schedules"),
            }
            # Ledger shape: top procedure codes for pay vs charge
            live["ledgerTopProcedureCodes"] = [
                {
                    "procedure": r[0],
                    "n": r[1],
                    "paySum": r[2],
                    "adjSum": r[3],
                    "prodSum": r[4],
                }
                for r in con.execute(
                    """
                    SELECT procedure, COUNT(*),
                      ROUND(SUM(COALESCE(cash,0)+COALESCE("check",0)+COALESCE(credit,0)),2),
                      ROUND(SUM(COALESCE(prod_adj,0)+COALESCE(pay_adj,0)),2),
                      ROUND(SUM(COALESCE(prod,0)+COALESCE(charges,0)),2)
                    FROM sd_account_transactions
                    GROUP BY 1 ORDER BY 2 DESC LIMIT 12
                    """
                )
            ]
            live["claimsByPayer"] = [
                {"payer": r[0], "n": r[1], "billed": r[2]}
                for r in con.execute(
                    """
                    SELECT COALESCE(NULLIF(TRIM(payer),''),'(empty)'), COUNT(*),
                           ROUND(SUM(COALESCE(total_fee, claim_amount)),2)
                    FROM sd_claims GROUP BY 1 ORDER BY 2 DESC LIMIT 12
                    """
                )
            ]
            live["insuranceNameSample"] = [
                {"name": r[0], "n": r[1]}
                for r in con.execute(
                    """
                    SELECT insurance_name, COUNT(*) FROM sd_patient_insurance
                    WHERE insurance_name IS NOT NULL AND TRIM(insurance_name)!=''
                    GROUP BY 1 ORDER BY 2 DESC LIMIT 10
                    """
                )
            ]
        finally:
            con.close()

    # Export file presence
    export_root = Path(r"C:\SoftDentFinancialExports")
    hits = []
    if export_root.is_dir():
        for pat in (
            "insurance_payments*.csv",
            "insurance_payment_analysis*.csv",
            "InsurancePayment*.csv",
            "procedure_codes*.csv",
        ):
            hits.extend(str(p) for p in export_root.glob(pat) if p.is_file())
    live["insurancePaymentCsvFound"] = hits[:20]
    live["insurancePaymentCsvCount"] = len(hits)

    try:
        from softdent_treatment_planning import treatment_planning_status  # noqa: E402

        live["treatmentPlanningStatus"] = treatment_planning_status()
    except Exception as exc:  # noqa: BLE001
        live["treatmentPlanningStatusError"] = f"{type(exc).__name__}:{exc}"

    try:
        from softdent_outstanding_claims_bridge import (  # noqa: E402
            build_outstanding_claims_by_carrier_bridge,
        )

        bridge = build_outstanding_claims_by_carrier_bridge(write_inbox=False)
        live["claimsBridge"] = {
            "gapCode": bridge.get("gapCode"),
            "named": (bridge.get("claims") or {}).get("namedPayerClaimCount"),
            "unnamed": (bridge.get("claims") or {}).get("unnamedPayerClaimCount"),
            "billed": (bridge.get("claims") or {}).get("billedTotal"),
            "agingIns": (bridge.get("aging") or {}).get("outstandingInsuranceTotal"),
        }
    except Exception as exc:  # noqa: BLE001
        live["claimsBridgeError"] = f"{type(exc).__name__}:{exc}"

    return json.dumps(live, indent=2, default=str)[:14000]


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
        ("MOONSHOT_SOFTDENT_ADA_PAYER_TX_CONSULT_2026-07-10.md", 2800),
        ("MOONSHOT_SOFTDENT_ADA_PAYER_TX_APPLIED_2026-07-10.md", 2200),
        ("MOONSHOT_PAYER_ATTRIBUTION_REFRESH_HAL10581_APPLIED_2026-07-13.md", 2000),
        ("MOONSHOT_OUTSTANDING_CLAIMS_BRIDGE_HAL10580_APPLIED_2026-07-13.md", 1400),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Give the HOW-TO with ALL current data. CONSULT ONLY — do not apply code.\n"
        "Code for Insurance Payment Analysis ingest already shipped (hal-10400); "
        "live sd_insurance_payment_lines=0 so the blocker is OPS export, not coding.\n"
        "Do NOT recommend inventing InsCo×ADA from ledger code 2/51 joins.\n\n"
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
        headers["X-Title"] = "NR2 InsCo x ADA HOW-TO Consult"
    print("Calling Moonshot AI (InsCo x ADA HOW-TO — consult only)...")

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
    (OUT / f"moonshot_insco_ada_howto_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10576"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — How to Derive InsCo × ADA Paid-After-Write-Off (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** ADA payer TX consult 2026-07-10 + apply hal-10400; HAL-10581 attribution  \n"
        f"**Script:** `scripts/run_moonshot_insco_ada_howto_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    doc = DOCS / f"MOONSHOT_INSCO_ADA_HOWTO_{DATE}.md"
    out = OUT / f"MOONSHOT_INSCO_ADA_HOWTO_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(out)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
