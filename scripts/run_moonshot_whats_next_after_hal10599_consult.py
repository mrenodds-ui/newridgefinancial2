"""Moonshot AI — What's next after HAL-10599 company-master catalog expand.

CONSULT ONLY. Operator asked to run what we just did through Moonshot.
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
NR2 = REPO / "NewRidgeFinancial2"
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
    "now run what you did through moonshot ai for a consult"
)

SYSTEM = """You are Moonshot AI — principal financial engineer + compliance auditor
for NR2 Apex HAL SoftDent RCM.

Operator asked for a CONSULT after HAL-10598 + HAL-10599 just shipped on
fix/main-validate-ci (commits 6e5ba62, cc76c70). BUILD_ID=hal-10599.

CONSULT ONLY — DO NOT claim you applied code. empty != $0.
No SoftDent write-back. Do not invent Ins Plan Register dollars, gold lines,
carrier payment amounts, or clear insufficient/no_settlement without ledger
settlements. Do NOT redo HAL-10580–10599 as greenfield — build ON them.

JUST SHIPPED:
HAL-10598 — SoftDent insurance companies CSV → insurance_company_reference
- Source: C:\\New folder\\artifacts\\softdent_insurance_companies_2026-06-06.csv
- Live: 446 total · 215 likely_active · 228 discontinued
- Spine overlap likely_active: 71 · likely_active not in spine: 144
- Module: softdent_insurance_company_reference.py
- CLI: scripts/import_softdent_insurance_companies_csv.py
- Catalog status surfaces companyReference
- Does NOT invent InsCo×ADA dollars

HAL-10599 — Expand staff InsCo×ADA catalog to company master × ADA universe
- expand_catalog_rows_with_company_master on export
- Live staff grid: 30,024 cells = 216 companies × 139 ADAs
- Spine cells unchanged: 2,274 · exact usable unchanged: 46
- Pad: 28,653 credibility=no_settlement with null $ / null %
  (source=company_master_no_spine; empty != $0)
- CSV: C:\\SoftDentFinancialExports\\insco_ada_catalog_matrix_2026-07-13.csv
- Inbox: app_data\\nr2\\document_inbox\\softdent\\softdent_insco_ada_catalog_matrix.csv
- Package: softdent_insco_ada_catalog_matrix.py (DEF HAL-10599)

STAFF ASK THAT DROVE THIS (now answered by CSV, not by inventing $):
"list of all ada codes with all insurance companies we take and treatment
plan variances" — grid exists; dollars only where ledger 2/51 samples exist.

STILL OPEN / GROUND TRUTH:
- Gold CSV missing: sd_insurance_payment_lines=0, gapCode=GOLD_CSV_MISSING
- SoftDent v19.1.4: Insurance Income path is Print Preview only (HAL-10597);
  visual audit ≠ gold ingest
- Exact usable InsCo×ADA cells still only 46; most spine cells insufficient
- 144 likely_active names not in settlement spine (name variants / no episodes)
- Register Ins Plan Collections may be $0 for periods — do not invent
- ERA-835 still procurement-gated unless live files appear

OPEN CANDIDATES (pick ONE highest-leverage NEXT):
1) CODE: Fuzzy/alias match company master ↔ spine carrier names so the 144
   "not in spine" are reconciled where they are the same payer under aliases
   (still no invent $; only join existing settlements to master IDs)
2) CODE: Staff catalog UX — filter/sort no_settlement vs usable; HAL chips for
   "companies we take with $0 history"; export likely_active-only views
3) CODE: Grow exact usable carefully (secondary-ins, same-day settlement,
   credibility floors) — only with honesty gates; do not lower floors to fake 46→N
4) CODE/OPS: Uncovered ledger CDT playbook (47 CDTs seen in TX, no 2/51 cell)
5) CODE: Honesty CI gate — fail if financial widgets regress null→$0.00
6) CODE: money_to_api bijective string/cent path residual (if still float bridge)
7) OPS+CODE: Gold CSV / ERA835 first-drop — ONLY if real files exist on disk
8) OPS: SoftDent Insurance Income Excel still product-blocked — do not pretend

What NOT to redo: SoftDent write-back; invent gold from ledger/DaySheet;
invent InsCo×ADA $ for no_settlement; pretend Insurance.xlsx is on Desktop;
Register re-export to invent Ins Plan>0; GitHub/PR as primary next;
re-import company CSV without new source; rebuild spine as greenfield.

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
        "priorCommits": {
            "hal10598": "6e5ba62",
            "hal10599": "cc76c70",
        },
        "appliedDocs": [
            "MOONSHOT_APPLIED_HAL10598_INSURANCE_COMPANY_REFERENCE_2026-07-13.md",
            "MOONSHOT_APPLIED_HAL10599_COMPANY_MASTER_CATALOG_EXPAND_2026-07-13.md",
        ],
        "operatorAsk": OPERATOR_REQUEST_VERBATIM,
    }
    try:
        sys.path.insert(0, str(NR2))
        from apex_backend import BUILD_ID  # noqa: E402
        from softdent_gold_payment_pipeline import audit_gold_payment_pipeline  # noqa: E402
        from softdent_insco_ada_catalog_matrix import (  # noqa: E402
            PACKAGE_BUILD_ID,
            catalog_matrix_status,
            list_catalog_ada_universe,
            list_catalog_company_universe,
        )
        from softdent_insurance_company_reference import (  # noqa: E402
            insurance_company_reference_status,
        )
        from softdent_gold_csv_drop_ops import PACKAGE_BUILD_ID as GOLD_OPS_BUILD  # noqa: E402

        live["buildId"] = BUILD_ID
        live["catalogPackageBuildId"] = PACKAGE_BUILD_ID
        live["goldOpsPackageBuildId"] = GOLD_OPS_BUILD
        live["buildIdCoupled"] = BUILD_ID == PACKAGE_BUILD_ID == "hal-10599"

        gold = audit_gold_payment_pipeline()
        live["gold"] = {
            "gapCode": gold.get("gapCode"),
            "paymentLines": gold.get("paymentLines"),
            "treatmentEstimates": gold.get("treatmentEstimates"),
        }

        st = catalog_matrix_status()
        live["catalog"] = {
            k: st.get(k)
            for k in (
                "ok",
                "totalCells",
                "spineCells",
                "exactUsableCells",
                "publishedCells",
                "insufficientCells",
                "carriers",
                "distinctAdaInSpine",
                "ledgerCdtUniverse",
                "uncoveredCount",
                "masterExpandedCells",
                "masterCompanyUniverse",
                "masterAdaUniverse",
                "noSettlementPadCells",
                "companyReference",
                "emptyIsNotZero",
            )
        }
        live["companyUniverseCount"] = len(list_catalog_company_universe())
        live["adaUniverseCount"] = len(list_catalog_ada_universe())
        live["companyReference"] = insurance_company_reference_status()

        exports = Path(r"C:\SoftDentFinancialExports")
        if exports.is_dir():
            csvs = sorted(exports.glob("insco_ada_catalog_matrix_*.csv"), reverse=True)
            live["catalogCsv"] = {
                "path": str(csvs[0]) if csvs else None,
                "bytes": csvs[0].stat().st_size if csvs else None,
            }
            live["companyMasterCsvStable"] = str(
                exports / "softdent_insurance_companies.csv"
            ) if (exports / "softdent_insurance_companies.csv").is_file() else None
            live["eraLikeFilesSample"] = sorted(
                {
                    p.name
                    for pat in ("*835*", "*era*", "*ERA*", "*remit*")
                    for p in exports.glob(pat)
                }
            )[:20]

        inbox = (
            REPO
            / "app_data"
            / "nr2"
            / "document_inbox"
            / "softdent"
            / "softdent_insco_ada_catalog_matrix.csv"
        )
        live["inboxCatalogCsv"] = {
            "path": str(inbox) if inbox.is_file() else None,
            "bytes": inbox.stat().st_size if inbox.is_file() else None,
        }

        db = Path(r"C:\SoftDentFinancialExports\softdent_financial_analytics.db")
        if db.is_file():
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                for table, key in (
                    ("sd_insurance_payment_lines", "paymentLines"),
                    ("era_835_payments", "era835"),
                    ("insurance_company_reference", "companyRefRows"),
                    ("insco_ada_probabilistic_estimates", "spineEstimateRows"),
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
    return json.dumps(live, indent=2, default=str)[:18000]


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
        ("MOONSHOT_APPLIED_HAL10599_COMPANY_MASTER_CATALOG_EXPAND_2026-07-13.md", 3500),
        ("MOONSHOT_APPLIED_HAL10598_INSURANCE_COMPANY_REFERENCE_2026-07-13.md", 2500),
        ("MOONSHOT_APPLIED_HAL10596_INSCO_ADA_CATALOG_STAFF_2026-07-13.md", 2000),
        ("MOONSHOT_APPLIED_HAL10597_GOLD_OPS_V19_2026-07-13.md", 1800),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "HAL-10598 company master + HAL-10599 catalog expand SHIPPED "
        "(6e5ba62, cc76c70). Staff grid is 30,024 cells with honest "
        "no_settlement null dollars. Gold still GOLD_CSV_MISSING. "
        "Pick THE next package. CONSULT ONLY — do not apply.\n\n"
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
        headers["X-Title"] = "NR2 Whats Next After HAL-10599"
    print("Calling Moonshot AI (what's next after 10599 — consult only)...")

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
    (OUT / f"moonshot_whats_next_after_hal10599_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10599"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — What's Next After HAL-10599 Company-Master Catalog "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** HAL-10598 (`6e5ba62`) · HAL-10599 (`cc76c70`)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_hal10599_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves (`proceed`).\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_HAL10599_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_HAL10599_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(out)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
