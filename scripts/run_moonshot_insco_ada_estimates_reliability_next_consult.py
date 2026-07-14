"""Moonshot AI — What's next for InsCo×ADA probabilistic estimates / reliability / report.

CONSULT ONLY. Operator: ask moonshot how to proceed with those estimates and reliability and report.
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
    "ask moonshot ai how to proceed with those estimates and relaiablity and report"
)

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL + SoftDent RCM.

Operator asks how to PROCEED with the NEW InsCo×ADA probabilistic estimates,
their RELIABILITY, and the REPORT (HAL-10582 just shipped on fix/main-validate-ci).

CONSULT ONLY — DO NOT claim you applied code. empty != $0.
No SoftDent write-back. Do not invent Ins Plan Register dollars or carrier names.
Do NOT redo HAL-10581 attribution, HAL-10580 claims bridge, or invent ledger→ADA joins
beyond what 10582 already labels as exact/inferred.

JUST COMPLETED (d028527 — HAL-10582 probabilistic InsCo×ADA):
- softdent_insco_ada_probabilistic.py builds estimates from ledger codes 2 (pay) +
  51/52 (write-off) + sd_patient_insurance primary carrier
- Tiers: exact (1 ADA lookback), inferred (2–3 ADA proportional), low (4+ not published)
- Credibility floors: exact usable n≥10, exact high n≥30; inferred usable n≥30 / stronger ≥75
- Live: ~24mo window; publishedCells=124; highCredibilityCells=2; totalCells~1973
- Event mix ~ exact 702 / inferred 8449 / low 4520 — most days multi-ADA
- Reports written to SoftDentFinancialExports + softdent inbox JSON
- Gold path (hal-10400 payment lines) STILL empty (sd_insurance_payment_lines=0)
- SoftDent Writeoff Totals: Excel not usable; Print Preview; practice posts WO as 51
  (Carestream report often expects 50.90) — preview can show $0

Pick THE single best NEXT package to improve reliability and/or productize the report
for HAL/ops. Prefer additive local CODE/OPS. Avoid GitHub/PR as primary.

OPEN CANDIDATES (pick ONE):
1) CODE: HAL board-action + widget/API surfacing only high/usable exact cells with
   explicit credibility badges; refuse inferred unless staff asks "inferred ok"
2) CODE: Reliability uplift — tighten lookback, require same-claim-day charge+pay,
   secondary-insurance exclusion, bootstrap CIs / median-only publish
3) OPS+CODE: SoftDent payment-line / Insurance Payment Distribution Print Preview
   capture playbook OR File output if any — only if REAL SoftDent path exists;
   do not pretend Excel works when operator said Excel unavailable
4) CODE: Cross-validate probabilistic cells vs fee_schedule / Sensei plan allowed
   when present; flag outliers
5) OPS: Expand history / coverage quality (re-run Sensei insurance; year-chunk TX
   already multi-year) — only if live snapshot shows a clear gap
6) CODE: Side-by-side report: probabilistic vs treatment_planning_estimates when
   payment CSV finally lands (scaffold now)

What NOT to redo: invent Ins Plan $, Register re-export, SoftDent write-back,
claiming ledger estimates are contractual.

OUTPUT (strict markdown):
# Verdict (one sentence — THE next package)
## 0. Operator Intent (verbatim)
## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
## 2. Reliability posture (what 124 published / 2 high means; what to trust)
## 3. How to use the report in HAL/ops (display rules)
## 4. Runner-ups (2–3, why not now)
## 5. What NOT to redo
## 6. Acceptance criteria
## 7. Executive Summary (5 bullets)
## 8. Approval checklist
DO NOT APPLY CODE. Prefer one clear next over a laundry list.
"""


def _live_snapshot() -> str:
    live: dict = {
        "prior": "d028527 HAL-10582 InsCo×ADA probabilistic",
        "module": "NewRidgeFinancial2/softdent_insco_ada_probabilistic.py",
        "appliedDoc": "MOONSHOT_INSCO_ADA_PROBABILISTIC_HAL10582_APPLIED_2026-07-13.md",
        "howtoDoc": "MOONSHOT_INSCO_ADA_HOWTO_2026-07-13.md",
        "writeoff51Doc": "MOONSHOT_WRITEOFF_CODE51_ADA_PRINT_PREVIEW_2026-07-13.md",
        "reportMd": r"C:\SoftDentFinancialExports\insco_ada_probabilistic_report_2026-07-12.md",
        "reportJson": r"C:\SoftDentFinancialExports\insco_ada_probabilistic_report_2026-07-12.json",
        "inboxJson": "app_data/nr2/document_inbox/softdent/softdent_insco_ada_probabilistic.json",
        "operatorNotes": [
            "Excel not available for Writeoff Totals — Print Preview only",
            "Insurance write-off SoftDent code is 51 (by ADA on SoftDent report when populated)",
            "Ledger 51/2 rows lack ADA; 10582 allocates via lookback",
        ],
    }
    try:
        sys.path.insert(0, str(REPO / "NewRidgeFinancial2"))
        from apex_backend import BUILD_ID  # noqa: E402

        live["buildId"] = BUILD_ID
        from softdent_insco_ada_probabilistic import (  # noqa: E402
            CREDIBILITY,
            probabilistic_report_status,
        )

        live["status"] = probabilistic_report_status()
        live["credibilityRules"] = {
            k: CREDIBILITY[k] for k in CREDIBILITY if k != "honesty"
        }
        live["honesty"] = CREDIBILITY.get("honesty")

        db = Path(r"C:\SoftDentFinancialExports\softdent_financial_analytics.db")
        if db.is_file():
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                live["sd_insurance_payment_lines"] = int(
                    con.execute("SELECT COUNT(*) FROM sd_insurance_payment_lines").fetchone()[0]
                    or 0
                )
                live["treatment_planning_estimates"] = int(
                    con.execute("SELECT COUNT(*) FROM treatment_planning_estimates").fetchone()[0]
                    or 0
                )
                live["topPublished"] = [
                    {
                        "carrier": r[0],
                        "ada": r[1],
                        "tier": r[2],
                        "cred": r[3],
                        "n": r[4],
                        "paidMed": r[5],
                        "woMed": r[6],
                    }
                    for r in con.execute(
                        """
                        SELECT insurance_company, ada_code, tier, credibility, sample_size,
                               paid_median, write_off_median
                        FROM insco_ada_probabilistic_estimates
                        WHERE credibility != 'insufficient'
                        ORDER BY
                          CASE credibility WHEN 'high' THEN 0 WHEN 'usable' THEN 1 ELSE 2 END,
                          sample_size DESC
                        LIMIT 12
                        """
                    )
                ]
            finally:
                con.close()
    except Exception as exc:  # noqa: BLE001
        live["error"] = f"{type(exc).__name__}:{exc}"
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
        ("MOONSHOT_INSCO_ADA_PROBABILISTIC_HAL10582_APPLIED_2026-07-13.md", 2800),
        ("MOONSHOT_INSCO_ADA_HOWTO_2026-07-13.md", 2000),
        ("MOONSHOT_WRITEOFF_CODE51_ADA_PRINT_PREVIEW_2026-07-13.md", 1600),
        ("MOONSHOT_SOFTDENT_ADA_PAYER_TX_APPLIED_2026-07-10.md", 1200),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "HAL-10582 probabilistic InsCo×ADA report just shipped (124 published, 2 high). "
        "Payment-analysis gold path still empty. Pick THE next package for estimates + "
        "reliability + report. CONSULT ONLY.\n\n"
        f"## LIVE SNAPSHOT\n{live}\n\n"
        + "\n\n".join(excerpts)
    )
    payload = {
        "model": model,
        "temperature": 1.0,
        "max_tokens": 8000,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 InsCo ADA Estimates Reliability Next"
    print("Calling Moonshot AI (estimates/reliability/report — consult only)...")

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
    (OUT / f"moonshot_insco_ada_estimates_reliability_next_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10576"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — What's Next for InsCo×ADA Estimates / Reliability / Report "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior:** HAL-10582 probabilistic InsCo×ADA (`d028527`)  \n"
        f"**Script:** `scripts/run_moonshot_insco_ada_estimates_reliability_next_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_INSCO_ADA_ESTIMATES_RELIABILITY_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_INSCO_ADA_ESTIMATES_RELIABILITY_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(out)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
