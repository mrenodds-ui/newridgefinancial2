"""Moonshot AI — Confirm HAL-10601 TP carrier-alias wiring (CONSULT ONLY).

Operator: again confer with moonshot ai what you just did and consult only
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
    "again confer with moonshot ai what you just did and consult only"
)

SYSTEM = """You are Moonshot AI — principal financial engineer + compliance auditor
for NR2 Apex HAL SoftDent RCM / treatment planning.

Operator wants CONFIRMATION of what was just applied (HAL-10601) and THE single
best NEXT package. CONSULT ONLY — DO NOT claim you applied new code here.
empty != $0. No SoftDent write-back. Do not invent gold lines or InsCo×ADA $.

JUST APPLIED (commit 58e05c0 on fix/main-validate-ci, BUILD_ID=hal-10601):
HAL-10601 — TP Payer Resolution via Accepted Carrier Alias
(exactly your prior recommendation from MOONSHOT_CONFIRM_HAL10600_TREATMENT_PLANNING)

Shipped:
- resolve_accepted_alias_for_tp() in softdent_carrier_alias.py
- lookup_treatment_estimate in softdent_treatment_planning.py:
  1) gold treatment_planning_estimates first
  2) accepted alias only (confidence=auto + review_status=accepted)
  3) spine lookup with spine_carrier_name
  4) source=ledger_episode_5yr_via_alias when alias used
  5) pending manuals (confidence=manual) → blockedPending /
     source=carrier_alias_pending / insufficient / null $ / HAL message
- treatment_planning_status: tpCodeUsesCarrierAlias=true, def=HAL-10601
- Tests: test_hal10601_tp_carrier_alias.py
- Docs: MOONSHOT_APPLIED_HAL10601_TP_CARRIER_ALIAS_2026-07-13.md

Live probes after apply:
- Aetna Healthcare × D2391 → found/sufficient/viaAlias, paid $60.80,
  spine=AETNA, source=ledger_episode_5yr_via_alias, emptyIsNotZero
- ANTHEM - 188 (pending) → blockedPending, insufficient, null $, no dollars shown
- tpCodeUsesCarrierAlias=true

PRIOR STILL TRUE:
- HAL-10600 alias table: 107 auto accepted, 19 manual pending, 89 rejected
- Gold still GOLD_CSV_MISSING / paymentLines=0
- Catalog staff grid + no_settlement pad remain; exactUsableCells=46
- Pending manuals must NOT be blindly accepted (Guardian→Aetna etc. dubious)

YOUR JOB:
A) CONFIRM APPLY — Did HAL-10601 match your recommended package? Deviations?
   Residual risks?
B) Recommend THE single best NEXT package now (not a laundry list).

OPEN CANDIDATES (pick ONE):
1) CODE: TP chip surfaces masterCompanyId + spineCarrierName + viaAlias on UI
   (cosmetic metadata after #1 foundation)
2) OPS: HAL review of 19 pending manuals (accept/reject) — parallel track
3) CODE: Honesty CI gate — fail if TP/widgets regress null→$0.00
4) CODE: Grow usable InsCo×ADA carefully (secondary-ins) — after identity solid
5) OPS+CODE: Gold CSV / ERA — ONLY if real files exist on disk
6) CODE: Uncovered ledger CDT playbook (47 CDTs)

What NOT to redo: SoftDent write-back; invent gold; accept all 19 pending blindly;
force ≤20 alias gap; rebuild spine greenfield; re-wire 10601; GitHub/PR as primary.

OUTPUT (strict markdown):
# Verdict (one sentence — confirm HAL-10601 + THE next package)
## 0. Operator Intent (verbatim)
## 1. Confirmation of HAL-10601 apply (pass/fail; deviations; residual risks)
## 2. Recommended NEXT (name, why now, effort, REAL files, validation gate)
## 3. Why this beats other candidates now
## 4. Runner-ups (2–3)
## 5. What NOT to redo
## 6. Acceptance criteria
## 7. Executive Summary (5 bullets)
## 8. Approval checklist
DO NOT APPLY CODE.
"""


def _live_snapshot() -> str:
    live: dict = {
        "commit": "58e05c0",
        "buildExpected": "hal-10601",
        "operatorAsk": OPERATOR_REQUEST_VERBATIM,
        "appliedDocs": [
            "MOONSHOT_APPLIED_HAL10601_TP_CARRIER_ALIAS_2026-07-13.md",
            "MOONSHOT_CONFIRM_HAL10600_TREATMENT_PLANNING_2026-07-13.md",
            "MOONSHOT_APPLIED_HAL10600_CARRIER_ALIAS_2026-07-13.md",
        ],
    }
    try:
        sys.path.insert(0, str(NR2))
        from apex_backend import BUILD_ID  # noqa: E402
        from softdent_carrier_alias import carrier_alias_status  # noqa: E402
        from softdent_gold_payment_pipeline import audit_gold_payment_pipeline  # noqa: E402
        from softdent_insco_ada_catalog_matrix import catalog_matrix_status  # noqa: E402
        from softdent_treatment_planning import (  # noqa: E402
            lookup_treatment_estimate,
            treatment_planning_status,
        )

        live["buildId"] = BUILD_ID
        live["buildIdCoupled"] = BUILD_ID == "hal-10601"
        tp_src = (NR2 / "softdent_treatment_planning.py").read_text(encoding="utf-8")
        live["tpCodeUsesCarrierAliasImport"] = "softdent_carrier_alias" in tp_src
        live["tpCodeUsesCarrierAlias"] = "resolve_accepted_alias_for_tp" in tp_src
        live["treatmentPlanningStatus"] = {
            k: treatment_planning_status().get(k)
            for k in (
                "ok",
                "paymentLines",
                "estimates",
                "ledgerSpineExactUsable",
                "fallbackSource",
                "tpCodeUsesCarrierAlias",
                "emptyIsNotZero",
                "def",
                "hint",
            )
        }
        live["carrierAlias"] = {
            k: carrier_alias_status().get(k)
            for k in (
                "ok",
                "autoAccepted",
                "fuzzyAutoAccepted",
                "exactIdentity",
                "manualPending",
                "rejected",
                "likelyActiveNotInSpine",
                "acceptanceGateMet",
            )
        }
        gold = audit_gold_payment_pipeline()
        live["gold"] = {
            "gapCode": gold.get("gapCode"),
            "paymentLines": gold.get("paymentLines"),
            "treatmentEstimates": gold.get("treatmentEstimates"),
        }
        live["catalog"] = {
            k: catalog_matrix_status().get(k)
            for k in (
                "exactUsableCells",
                "noSettlementPadCells",
                "masterExpandedCells",
                "emptyIsNotZero",
            )
        }

        def _probe(payer: str, ada: str) -> dict:
            r = lookup_treatment_estimate(payer=payer, ada_code=ada)
            est = r.get("estimate") if isinstance(r.get("estimate"), dict) else {}
            chip = r.get("chip") if isinstance(r.get("chip"), dict) else {}
            return {
                "found": r.get("found"),
                "sufficient": r.get("sufficient"),
                "viaAlias": r.get("viaAlias"),
                "blockedPending": r.get("blockedPending"),
                "source": r.get("source"),
                "credibility": r.get("credibility"),
                "def": r.get("def"),
                "spineCarrierName": r.get("spineCarrierName") or est.get("spineCarrierName"),
                "masterCompanyId": r.get("masterCompanyId") or est.get("masterCompanyId"),
                "paidAmountAvg": est.get("paidAmountAvg"),
                "showDollars": chip.get("showDollars"),
                "emptyIsNotZero": chip.get("emptyIsNotZero"),
            }

        live["probes"] = {
            "aetnaHealthcare_D2391": _probe("Aetna Healthcare", "D2391"),
            "aetna_D2391": _probe("AETNA", "D2391"),
            "anthem188_pending_D1110": _probe("ANTHEM - 188", "D1110"),
        }

        db = Path(r"C:\SoftDentFinancialExports\softdent_financial_analytics.db")
        if db.is_file():
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                live["paymentLines"] = int(
                    con.execute("SELECT COUNT(*) FROM sd_insurance_payment_lines").fetchone()[0]
                    or 0
                )
                live["tpEstimateRows"] = int(
                    con.execute("SELECT COUNT(*) FROM treatment_planning_estimates").fetchone()[0]
                    or 0
                )
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
        ("MOONSHOT_APPLIED_HAL10601_TP_CARRIER_ALIAS_2026-07-13.md", 3500),
        ("MOONSHOT_CONFIRM_HAL10600_TREATMENT_PLANNING_2026-07-13.md", 4000),
        ("MOONSHOT_APPLIED_HAL10600_CARRIER_ALIAS_2026-07-13.md", 2500),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Confirm HAL-10601 apply vs your prior TP recommendation. Then pick THE "
        "next package. CONSULT ONLY — do not apply.\n\n"
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
        headers["X-Title"] = "NR2 Confirm HAL-10601"
    print("Calling Moonshot AI (confirm 10601 — consult only)...")

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
    (OUT / f"moonshot_confirm_hal10601_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10601"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — Confirm HAL-10601 TP Carrier Alias "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior apply:** HAL-10601 (`58e05c0`)  \n"
        f"**Script:** `scripts/run_moonshot_confirm_hal10601_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves (`proceed`).\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    doc = DOCS / f"MOONSHOT_CONFIRM_HAL10601_{DATE}.md"
    out = OUT / f"MOONSHOT_CONFIRM_HAL10601_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(out)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
