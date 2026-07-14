"""Moonshot AI — What's next after page-inspect fix-all continue.

CONSULT ONLY. Operator: next
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.error
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

OPERATOR_REQUEST_VERBATIM = "next"

SYSTEM = """You are Moonshot AI — principal financial engineer + compliance auditor
for NR2 Apex HAL SoftDent RCM / treatment planning.

Operator said: next
CONSULT ONLY — DO NOT claim you applied code. empty != $0.
No SoftDent write-back. Do NOT invent gold payment lines, InsCo×ADA $, or
Register collections. Do NOT force-match rejected aliases.
Do NOT redo HAL-10588–10608 or the page-inspect fix-all as greenfield — build ON them.
Do NOT recommend more PWImages JPEG/PDF OCR for settlement (10608 STOP policy).
Do NOT invent SoftDent SQL for financial empties (procedure-profitability, etc.).

JUST SHIPPED (commit 4899992 on fix/main-validate-ci, BUILD_ID=hal-10608):
Page-inspect fix-all CONTINUE:
- ZERO_VOLUME gapCodes on denial-pareto / preauth-aging-lanes / payer-change-alerts
- Library widgets call real seed_document_library (library page now active)
- find_account_aging_export skips derived softdent_ar_aging.csv; prefers real SoftDent
  account_aging.csv — outstanding-claims bridge now honest CLAIMS_AR_RECONCILE_MISMATCH
  (aging Outstanding Insurance $0 vs sd_claims billed) not false AGING_EXPORT_MISSING

PRIOR FIX-ALL (b67281b / 021ee69):
- schema/asset hal-10608 skew fixed
- AR aging CSV → softdent_ar_aging (prefer newer csv vs jsonl)
- patient_id hydrate for dossier / OM cards
- HAL actions recommend Gold CSV + ERA when gaps present
- Crash/perf + warming 429 repairs already shipped

LIVE RE-INSPECT AFTER CONTINUE:
- readiness fresh; AR dataset gaps []
- 142 active / 22 faulty / 13 honest / 0 crashed
- Library active
- SoftDent honest: GOLD_CSV_MISSING, ERA_835_REQUIRED, NO_PATIENT_CONTEXT,
  CLAIMS_AR_RECONCILE_MISMATCH
- Faulty leftovers mostly empty modules without feeds (financial scatter/pipeline/bridge,
  OM patient cards without patient_id, DEF-001 mirrors, narr/documents empties)

OPS CONTEXT:
- Carestream support ticket draft READY TO SUBMIT for line-item Insurance Payment CSV
  (v19.1.4 Print Preview only — no Excel on Insurance Income family)
- ERA 835 still procurement/enrollment gated
- Print Preview visual totals ≠ Gold

YOUR JOB:
Recommend THE single best NEXT package now (not a laundry list).

OPEN CANDIDATES (pick ONE):
1) OPS: Submit Carestream Gold CSV ticket + keep GOLD_CSV_MISSING honest until drop
2) OPS: ERA 835 clearinghouse enrollment + first real drop/ingest
3) CODE: Mark remaining empty financial/OM/narr widgets with honest gapCodes
   (ZERO_VOLUME / NO_PATIENT_CONTEXT / FEED_MISSING) so inspect counts stay clean
4) CODE: Default OM/SoftDent dossier to a real selectedPatient when one patient is
   already in session/UI (no invent; only if selectedPatient plumbing already exists)
5) CODE: Import-cache KPI fill coalescing / per-page fillProgress polish
   (note: crash/perf + warming backoff already partially shipped — only if residual)
6) CODE: Surface CLAIMS_AR_RECONCILE_MISMATCH staff briefing (ins $0 aging truth vs claims)
7) OPS: Staff accept/reject Coventry MEDIUM alias pending (only with evidence)

Prefer highest ROI that unblocks practice settlement truth without inventing $.
Prefer OPS when the only missing input is Carestream/ERA procurement.
Prefer CODE only when it removes false "faulty" noise or unblocks staff without inventing $.

What NOT to redo: SoftDent write-back; invent gold from Print Preview/OCR/DaySheet;
rebuild library_indexer.py / widget_resolver.py fiction; force TP aliases; more JPG OCR;
GitHub/PR as primary next.

OUTPUT (strict markdown):
# Verdict (one sentence — THE next package)
## 0. Operator Intent (verbatim)
## 1. Confirmation of page-inspect continue apply (pass/fail; residual risks)
## 2. Recommended NEXT (name, why now, effort, REAL files/actions, validation gate)
## 3. Why this beats other candidates now
## 4. Runner-ups (2–3)
## 5. What NOT to redo
## 6. Acceptance criteria
## 7. Executive Summary (5 bullets)
## 8. Approval checklist
DO NOT APPLY CODE.
"""


def _live_snapshot() -> str:
    sys.path.insert(0, str(NR2))
    live: dict = {
        "buildExpected": "hal-10608",
        "operatorAsk": OPERATOR_REQUEST_VERBATIM,
        "lastCommitHint": "4899992 page-inspect continue",
        "inspectSummary": {"active": 142, "faulty": 22, "honest": 13},
    }
    inspect = DOCS / "_nr2_page_inspect_after_continue.json"
    if inspect.is_file():
        try:
            live["inspect"] = json.loads(inspect.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            live["inspectError"] = f"{type(exc).__name__}:{exc}"
    try:
        from apex_backend import BUILD_ID
        from softdent_gold_era_settlement_hal10608 import gold_era_settlement_status
        from softdent_outstanding_claims_bridge import (
            build_outstanding_claims_by_carrier_bridge,
            find_account_aging_export,
        )
        from softdent_treatment_planning import resolve_analytics_db

        live["buildId"] = BUILD_ID
        aging = find_account_aging_export()
        live["agingPath"] = str(aging) if aging else None
        bridge = build_outstanding_claims_by_carrier_bridge(write_inbox=False)
        live["claimsBridge"] = {
            "gapCode": bridge.get("gapCode"),
            "agingOk": (bridge.get("aging") or {}).get("ok"),
            "agingAR": (bridge.get("aging") or {}).get("trueReceivablesTotal"),
            "agingIns": (bridge.get("aging") or {}).get("outstandingInsuranceTotal"),
            "claims": (bridge.get("claims") or {}).get("claimCount"),
        }
        st = gold_era_settlement_status()
        live["goldEra"] = {
            "ready": (st.get("readiness") or {}).get("ready"),
            "reason": (st.get("readiness") or {}).get("reason"),
            "gapGold": (st.get("gold") or {}).get("gapCode"),
            "paymentLines": (st.get("gold") or {}).get("paymentLines"),
            "gapEra": (st.get("era") or {}).get("gapCode"),
            "eraFileCount": (st.get("era") or {}).get("fileCount"),
        }
        db = resolve_analytics_db()
        live["dbPath"] = str(db)
        if db and Path(db).is_file():
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:

                def _c(t: str) -> int | None:
                    try:
                        return int(con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] or 0)
                    except Exception:
                        return None

                live["counts"] = {
                    "paymentLines": _c("sd_insurance_payment_lines"),
                    "settlementMatrix": _c("settlement_matrix"),
                    "stagingEligibility": _c("staging_eligibility_parameters"),
                    "sdClaims": _c("sd_claims"),
                }
            finally:
                con.close()
    except Exception as exc:  # noqa: BLE001
        live["error"] = f"{type(exc).__name__}:{exc}"
    return json.dumps(live, indent=2, default=str)[:24000]


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
        ("MOONSHOT_APPLIED_FIX_ALL_PAGE_INSPECT_2026-07-13.md", 4000),
        ("CARESTREAM_SUPPORT_TICKET_GOLD_CSV_2026-07-13.md", 2500),
        ("MOONSHOT_APPLIED_HAL10608_GOLD_ERA_SETTLEMENT_2026-07-13.md", 2000),
        ("MOONSHOT_WHATS_NEXT_AFTER_HAL10608_2026-07-13.md", 2000),
        ("MOONSHOT_OPS_GOLD_CSV_PROCUREMENT_PROCEED_2026-07-13.md", 2000),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "CONSULT ONLY — pick THE single best next package after page-inspect continue "
        "(commit 4899992).\n\n"
        f"## LIVE SNAPSHOT\n{live}\n\n" + "\n\n".join(excerpts)
    )

    payload = {
        "model": model,
        "temperature": 1.0,
        "max_tokens": 10000,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Whats Next After Page Inspect Continue"
    print("Calling Moonshot AI (whats next after page-inspect continue — consult only)...")

    req = urllib.request.Request(
        base_url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=1200) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        content = extract_message_content(raw)
        status = "ok"
    except Exception as exc:  # noqa: BLE001
        content = str(exc)
        status = "error"
        raw = {"error": content}
        try:
            if isinstance(exc, urllib.error.HTTPError) and exc.fp is not None:
                body = exc.read().decode("utf-8", errors="replace")
                raw = {"error": content, "body": body}
                content = f"{content}\n{body}"
        except Exception:
            pass

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (OUT / f"moonshot_whats_next_after_page_inspect_continue_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )

    header = (
        f"# Moonshot AI — What's Next After Page-Inspect Continue "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**UTC:** {stamp}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** hal-10608  \n"
        f"**Prior commit:** 4899992  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_page_inspect_continue_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves (`proceed`).\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_PAGE_INSPECT_CONTINUE_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_PAGE_INSPECT_CONTINUE_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(out)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
