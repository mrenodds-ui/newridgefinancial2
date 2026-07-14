"""Moonshot AI — What's next after HAL-10608 Gold/ERA settlement readiness.

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
Do NOT redo HAL-10588–10608 as greenfield — build ON them.
Do NOT recommend more PWImages JPEG/PDF OCR for settlement (10608 STOP policy).

JUST SHIPPED (commit 2f8e30b on fix/main-validate-ci, BUILD_ID=hal-10608):
HAL-10608 — Gold ∪ ERA settlement readiness + STOP PWImages OCR
- Single /api/apex/gold-era-settlement/status|run surface
- Readiness = GOLD_OK paymentLines>0 OR ERA inbox/ingest present
- Explicit ocrExpansionStopped / writesFromOcr=false
- settlement_matrix still hydrates ONLY from Gold CSV lines (ERA readiness ≠ invent matrix)
- Live typically: GOLD_CSV_MISSING, paymentLines=0 until SoftDent CSV drop

PRIOR STACK:
- HAL-10607 PWImages eligibility staging + remittance path warehouse (no OCR $)
- HAL-10605–10606 settlement_matrix + gold drop facilitation
- HAL-10600–10604 carrier aliases + TP + honesty CI
- Exact usable ledger InsCo×ADA still thin (~46) until gold
- ERA inbox tooling exists (apex_era835_pack) — procurement/drop gated

YOUR JOB:
Recommend THE single best NEXT package now (not a laundry list).

OPEN CANDIDATES (pick ONE):
1) OPS: SoftDent Gold CSV drop — land Insurance Payment Analysis CSV so
   paymentLines>0 and 10605/10608 acceptance can pass
   (save as C:\\SoftDentFinancialExports\\insurance_payments_YYYYMMDD.csv → Sync /
    gold-era-settlement/run). Note SoftDent v19 may lack named Payment Analysis menu;
    Print Preview alone ≠ gold.
2) OPS: ERA 835 first real drop into C:\\SoftDentFinancialExports\\era\\ then inbox ingest
3) CODE: TP UI chip — surface viaGold / viaAlias / pending / insufficient + 10608 readiness
4) OPS: Coventry MEDIUM pending accept/reject after staff glance (only with evidence)
5) CODE: Wire ERA aggregates into a non-settlement HAL posting backlog view (no matrix invent)
6) CODE: Staff catalog UX filter no_settlement vs usable
7) CODE: Secondary COB estimation (blocked until gold — likely why-not-now)

Prefer highest ROI that unblocks practice settlement truth without inventing $.
Prefer OPS when the only missing input is a real Gold CSV or ERA file.

What NOT to redo: SoftDent write-back; invent gold from ledger/DaySheet/Print Preview/
PWImages OCR; force-match TPAs/employers; rebuild spine greenfield; more Patient JPG OCR;
GitHub/PR as primary next.

OUTPUT (strict markdown):
# Verdict (one sentence — THE next package)
## 0. Operator Intent (verbatim)
## 1. Confirmation of HAL-10608 apply (pass/fail; residual risks)
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
    sys.path.insert(0, str(NR2))
    live: dict = {
        "buildExpected": "hal-10608",
        "operatorAsk": OPERATOR_REQUEST_VERBATIM,
        "lastCommitHint": "2f8e30b HAL-10608",
    }
    try:
        from apex_backend import BUILD_ID
        from softdent_gold_era_settlement_hal10608 import (
            gold_era_settlement_status,
            STOP_OCR_POLICY,
        )
        from softdent_treatment_planning import resolve_analytics_db

        live["buildId"] = BUILD_ID
        live["ocrPolicy"] = {
            k: STOP_OCR_POLICY.get(k)
            for k in (
                "ocrExpansionStopped",
                "writesFromOcr",
                "patientJpgOcrBlocked",
                "pdfRemittanceYield",
            )
        }
        st = gold_era_settlement_status()
        live["goldEra"] = {
            "ready": (st.get("readiness") or {}).get("ready"),
            "reason": (st.get("readiness") or {}).get("reason"),
            "lanes": (st.get("readiness") or {}).get("lanes"),
            "gapGold": (st.get("gold") or {}).get("gapCode"),
            "paymentLines": (st.get("gold") or {}).get("paymentLines"),
            "matrixCells": (st.get("gold") or {}).get("matrixCells"),
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
                    "warehouseRemittance": _c("warehouse_remittance_eobs"),
                    "carrierAlias": _c("carrier_alias"),
                }
            finally:
                con.close()
    except Exception as exc:  # noqa: BLE001
        live["error"] = f"{type(exc).__name__}:{exc}"
    return json.dumps(live, indent=2, default=str)[:20000]


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
        ("MOONSHOT_APPLIED_HAL10608_GOLD_ERA_SETTLEMENT_2026-07-13.md", 3000),
        ("MOONSHOT_PWIMAGES_JPEG_PDF_EOB_CONSULT_2026-07-13.md", 2500),
        ("MOONSHOT_APPLIED_HAL10607_PWIMAGES_ELIGIBILITY_PLAN_BRIDGE_2026-07-13.md", 2000),
        ("MOONSHOT_APPLIED_HAL10606_GOLD_DROP_FACILITATION_2026-07-13.md", 2000),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "CONSULT ONLY — pick THE single best next package after HAL-10608.\n\n"
        f"## LIVE SNAPSHOT\n{live}\n\n"
        + "\n\n".join(excerpts)
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
        headers["X-Title"] = "NR2 Whats Next After HAL-10608"
    print("Calling Moonshot AI (whats next after HAL-10608 — consult only)...")

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
    (OUT / f"moonshot_whats_next_after_hal10608_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )

    header = (
        f"# Moonshot AI — What's Next After HAL-10608 "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** hal-10608  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_hal10608_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves (`proceed`).\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_HAL10608_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_HAL10608_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(out)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
