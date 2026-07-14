"""Moonshot AI — Confirm HAL-10600 apply + treatment-planning impact.

CONSULT ONLY. Operator asked to confirm what was just done and for treatment planning.
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
    "confirm with moonshot ai what you just did and for treatment planning - consult only"
)

SYSTEM = """You are Moonshot AI — principal financial engineer + compliance auditor
for NR2 Apex HAL SoftDent RCM / treatment planning.

Operator wants a CONFIRMATION consult of what was just applied (HAL-10600) AND
explicit guidance for TREATMENT PLANNING. CONSULT ONLY — DO NOT claim you applied
new code in this response. empty != $0. No SoftDent write-back. Do not invent gold
lines, Ins Plan dollars, or InsCo×ADA amounts.

JUST APPLIED (commit d784bdd on fix/main-validate-ci, BUILD_ID=hal-10600):
HAL-10600 — Spine-to-Master Carrier Alias Reconciliation (your prior recommendation)
- Module: softdent_carrier_alias.py
- Schema: carrier_alias (spine_carrier_name, master_company_id, master_company_name,
  match_score, confidence auto|manual, review_status)
- Fuzzy: rapidfuzz Jaro-Winkler + token_set; first-4 / distinctive-token blocking;
  state + plan-code guards
- Bands: >85 auto-accept · 60–85 manual pending (HAL chip) · <60 reject
- CLI: scripts/reconcile_carrier_aliases.py
- CSV: C:\\SoftDentFinancialExports\\carrier_alias_mapping.csv
- Catalog join: masterCompanyId + spineCarrierName; source=alias_spine_settlement
  when master name maps to spine settlements (existing $ only)
- Live: 215 alias rows · 71 exact · 36 fuzzy auto · 107 auto total · 19 manual pending ·
  89 rejected · likelyActiveNotInSpineExact 144 → after-accepted 108 ·
  acceptanceGateMet(≤20)=false (honest: 89 are true no-spine orphans) ·
  exactUsableCells still 46 · no_settlement pad 28653→27838 · no synthetic
  probabilistic/gold rows invented

PRIOR CONTEXT STILL TRUE:
- HAL-10598 company master loaded (446 / 215 likely_active)
- HAL-10599 staff catalog grid 216 cos × 139 ADAs = 30,024 cells
- Gold path: sd_insurance_payment_lines=0, treatment_planning_estimates from gold=0,
  gapCode=GOLD_CSV_MISSING
- Treatment planning (softdent_treatment_planning.py):
  lookup_treatment_estimate tries gold treatment_planning_estimates first, then
  falls back to ledger spine via _ledger_spine_treatment_fallback /
  lookup_probabilistic_estimate (HAL-10585/87). It does NOT yet resolve payer
  names through carrier_alias before spine lookup.
- TP chip honesty: insufficient/empty never shown as $0.00

YOUR JOB (two parts):
A) CONFIRM APPLY — Did HAL-10600 match your recommended package? Call out any
   deviation, residual risk (esp. over-match / pending manuals), and whether
   refusing the ≤20 gap gate was correct honesty.
B) TREATMENT PLANNING — Given gold empty + aliases now exist, what is THE single
   best NEXT package for treatment planning with the program? Be concrete about
   whether TP lookup should resolve master→spine via accepted carrier_alias
   before probabilistic lookup, credibility rules, and what NOT to invent.

OPEN TP CANDIDATES (pick ONE highest leverage for PART B):
1) CODE: Wire lookup_treatment_estimate / _ledger_spine_treatment_fallback to
   resolve payer via accepted carrier_alias (master→spine) before spine query —
   reuse existing settlements only; pending aliases must NOT auto-resolve
2) CODE: TP chip shows masterCompanyId + spineCarrierName + alias confidence
   when estimate came via alias
3) CODE/OPS: Review/accept the 19 pending manuals (HAL) before TP uses them
4) CODE: Honesty CI for TP chip null→$0 regressions
5) OPS: Gold CSV / ERA still blocked — only if real files exist
6) CODE: Grow usable cells / secondary-ins — only after alias+TP identity layer

What NOT to redo: SoftDent write-back; invent gold from ledger; invent TP $ for
no_settlement; accept all 19 pending blindly; force ≤20 gap with unsafe matches;
rebuild spine greenfield; GitHub/PR as primary next.

OUTPUT (strict markdown):
# Verdict (one sentence — confirm HAL-10600 + THE next TP package name)
## 0. Operator Intent (verbatim)
## 1. Confirmation of HAL-10600 apply (pass/fail vs your consult; deviations; residual risks)
## 2. Recommended NEXT for treatment planning (name, why now, effort, REAL files, validation gate)
## 3. Why this beats other TP candidates now
## 4. Runner-ups (2–3)
## 5. What NOT to redo
## 6. Acceptance criteria
## 7. Executive Summary (5 bullets)
## 8. Approval checklist
DO NOT APPLY CODE. Prefer one clear next for treatment planning.
"""


def _live_snapshot() -> str:
    live: dict = {
        "commit": "d784bdd",
        "buildExpected": "hal-10600",
        "operatorAsk": OPERATOR_REQUEST_VERBATIM,
        "appliedDocs": [
            "MOONSHOT_APPLIED_HAL10600_CARRIER_ALIAS_2026-07-13.md",
            "MOONSHOT_WHATS_NEXT_AFTER_HAL10599_2026-07-13.md",
            "MOONSHOT_WHATS_NEXT_UNIFORM_ADA_TREATMENT_PLANNING_2026-07-13.md",
        ],
    }
    try:
        sys.path.insert(0, str(NR2))
        from apex_backend import BUILD_ID  # noqa: E402
        from softdent_carrier_alias import PACKAGE_BUILD_ID, carrier_alias_status  # noqa: E402
        from softdent_gold_payment_pipeline import audit_gold_payment_pipeline  # noqa: E402
        from softdent_insco_ada_catalog_matrix import catalog_matrix_status  # noqa: E402
        from softdent_insurance_company_reference import (  # noqa: E402
            insurance_company_reference_status,
        )
        from softdent_treatment_planning import (  # noqa: E402
            lookup_treatment_estimate,
            treatment_planning_status,
        )

        live["buildId"] = BUILD_ID
        live["aliasPackageBuildId"] = PACKAGE_BUILD_ID
        live["buildIdCoupled"] = BUILD_ID == PACKAGE_BUILD_ID == "hal-10600"
        live["carrierAlias"] = carrier_alias_status()
        live["companyReference"] = {
            k: insurance_company_reference_status().get(k)
            for k in (
                "ok",
                "total",
                "likelyActive",
                "spineOverlapLikelyActive",
                "likelyActiveNotInSpineExact",
                "likelyActiveNotInSpine",
                "carrierAlias",
            )
        }
        live["catalog"] = {
            k: catalog_matrix_status().get(k)
            for k in (
                "ok",
                "totalCells",
                "exactUsableCells",
                "masterExpandedCells",
                "noSettlementPadCells",
                "emptyIsNotZero",
            )
        }
        gold = audit_gold_payment_pipeline()
        live["gold"] = {
            "gapCode": gold.get("gapCode"),
            "paymentLines": gold.get("paymentLines"),
            "treatmentEstimates": gold.get("treatmentEstimates"),
        }
        try:
            live["treatmentPlanningStatus"] = {
                k: treatment_planning_status().get(k)
                for k in (
                    "ok",
                    "paymentLines",
                    "estimates",
                    "gapCode",
                    "emptyIsNotZero",
                    "message",
                )
            }
        except Exception as exc:  # noqa: BLE001
            live["treatmentPlanningStatus"] = {"error": f"{type(exc).__name__}:{exc}"}

        # Probe: TP lookup does NOT yet use alias — Aetna Healthcare should miss
        # exact spine name "AETNA" unless alias is wired (expect fallback behavior)
        try:
            live["tpProbeAetnaHealthcare"] = {
                k: lookup_treatment_estimate(
                    payer="Aetna Healthcare", ada_code="D1110"
                ).get(k)
                for k in (
                    "ok",
                    "found",
                    "sufficient",
                    "credibility",
                    "source",
                    "sampleSize",
                    "message",
                )
            }
            est = lookup_treatment_estimate(payer="Aetna Healthcare", ada_code="D1110").get(
                "estimate"
            )
            if isinstance(est, dict):
                live["tpProbeAetnaHealthcare"]["estimateCompany"] = est.get(
                    "insuranceCompany"
                )
                live["tpProbeAetnaHealthcare"]["paidAmountAvg"] = est.get("paidAmountAvg")
                live["tpProbeAetnaHealthcare"]["estimateSource"] = est.get("source")
            live["tpProbeAetnaExact"] = {
                k: lookup_treatment_estimate(payer="AETNA", ada_code="D1110").get(k)
                for k in ("ok", "found", "sufficient", "credibility", "source", "sampleSize")
            }
        except Exception as exc:  # noqa: BLE001
            live["tpProbeError"] = f"{type(exc).__name__}:{exc}"

        db = Path(r"C:\SoftDentFinancialExports\softdent_financial_analytics.db")
        if db.is_file():
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                for table, key in (
                    ("sd_insurance_payment_lines", "paymentLines"),
                    ("treatment_planning_estimates", "tpEstimateRows"),
                    ("carrier_alias", "carrierAliasRows"),
                    ("insco_ada_probabilistic_estimates", "spineEstimateRows"),
                ):
                    try:
                        live[key] = int(
                            con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0
                        )
                    except sqlite3.Error:
                        live[key] = None
                # Does TP code import carrier_alias?
                tp_src = (NR2 / "softdent_treatment_planning.py").read_text(encoding="utf-8")
                live["tpCodeUsesCarrierAlias"] = "carrier_alias" in tp_src or (
                    "softdent_carrier_alias" in tp_src
                )
            finally:
                con.close()

        mapping = Path(r"C:\SoftDentFinancialExports\carrier_alias_mapping.csv")
        live["aliasCsv"] = {
            "path": str(mapping) if mapping.is_file() else None,
            "bytes": mapping.stat().st_size if mapping.is_file() else None,
        }
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
        ("MOONSHOT_APPLIED_HAL10600_CARRIER_ALIAS_2026-07-13.md", 4000),
        ("MOONSHOT_WHATS_NEXT_AFTER_HAL10599_2026-07-13.md", 3500),
        ("MOONSHOT_WHATS_NEXT_UNIFORM_ADA_TREATMENT_PLANNING_2026-07-13.md", 2800),
        ("MOONSHOT_APPLIED_HAL10599_COMPANY_MASTER_CATALOG_EXPAND_2026-07-13.md", 1800),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Confirm HAL-10600 apply vs your prior consult. Then recommend THE next "
        "treatment-planning package. CONSULT ONLY — do not apply.\n\n"
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
        headers["X-Title"] = "NR2 Confirm HAL-10600 + Treatment Planning"
    print("Calling Moonshot AI (confirm 10600 + TP — consult only)...")

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
    (OUT / f"moonshot_confirm_hal10600_tp_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )
    build = "hal-10600"
    try:
        build = json.loads(live).get("buildId") or build
    except Exception:
        pass

    header = (
        f"# Moonshot AI — Confirm HAL-10600 + Treatment Planning "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** {build}  \n"
        f"**Prior apply:** HAL-10600 (`d784bdd`)  \n"
        f"**Script:** `scripts/run_moonshot_confirm_hal10600_treatment_planning_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves (`proceed`).\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    doc = DOCS / f"MOONSHOT_CONFIRM_HAL10600_TREATMENT_PLANNING_{DATE}.md"
    out = OUT / f"MOONSHOT_CONFIRM_HAL10600_TREATMENT_PLANNING_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(out)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
