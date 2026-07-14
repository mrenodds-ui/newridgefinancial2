"""Moonshot AI — What's next after HAL-10605 gold settlement matrix.

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
Register collections. Do NOT force-match the 75 rejected aliases.
Do NOT redo HAL-10588–10605 as greenfield — build ON them.

JUST SHIPPED (commit 99b17ef on fix/main-validate-ci, BUILD_ID=hal-10605):
HAL-10605 — Gold settlement_matrix + industry NEW HIGH aliases
- settlement_matrix schema + hydrate from sd_insurance_payment_lines via aliases
- TP prefer viaGold > viaAlias > viaLedger
- NEW HIGH: Great-west→CIGNA DENTAL; Kanawha→HUMANA DENTAL
- Coventry still MEDIUM pending; 75 rejected remain NONE
- Live: GOLD_CSV_MISSING, paymentLines=0, matrixCells=0, acceptanceGateMet=false
  (package ready; SoftDent Insurance Payment Analysis CSV never dropped)
- Honesty CI remains green; inventedGold=false

PRIOR STACK STILL TRUE:
- HAL-10600–10604 carrier aliases + TP wiring + honesty CI
- Exact usable ledger InsCo×ADA still ~46; staff catalog padded with no_settlement nulls
- Gold ETL (HAL-10588/10589/10597) already exists — 10605 adds matrix + prefer viaGold
- ERA-835 procurement-gated unless files appear

YOUR JOB:
Recommend THE single best NEXT package now (not a laundry list).

OPEN CANDIDATES (pick ONE):
1) OPS: SoftDent Gold CSV drop facilitation — operator/desktop playbook to land
   Insurance Payment Analysis CSV so 10605 acceptanceGate can pass
   (Reports → Insurance → Insurance Payment Analysis →
   C:\\SoftDentFinancialExports\\insurance_payments_YYYYMMDD.csv → Sync)
2) CODE: HAL UI chip — surface viaGold / viaAlias / pending / insufficient on TP
3) OPS: Accept or reject Coventry MEDIUM pending after staff glance
4) CODE: Address-field mining for leftover 75 (low ROI vs gold — you said why-not-now)
5) CODE: Secondary COB estimation (blocked until gold)
6) CODE/OPS: Uncovered ledger CDT playbook (47 CDTs)
7) OPS+CODE: ERA-835 first-drop — ONLY if real files exist on disk
8) CODE: Staff catalog UX filter no_settlement vs usable

What NOT to redo: SoftDent write-back; invent gold from ledger/DaySheet;
force-match Ahc/Bma/TPAs/employers; auto-accept Coventry without gold evidence;
rebuild spine greenfield; re-implement 10605; GitHub/PR as primary next.

OUTPUT (strict markdown):
# Verdict (one sentence — THE next package)
## 0. Operator Intent (verbatim)
## 1. Confirmation of HAL-10605 apply (pass/fail; residual risks)
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
        "commit": "99b17ef",
        "buildExpected": "hal-10605",
        "operatorAsk": OPERATOR_REQUEST_VERBATIM,
    }
    try:
        from apex_backend import BUILD_ID
        from softdent_carrier_alias import carrier_alias_status
        from softdent_gold_payment_pipeline import audit_gold_payment_pipeline
        from softdent_settlement_matrix import settlement_matrix_status

        live["buildId"] = BUILD_ID
        live["alias"] = {
            k: carrier_alias_status().get(k)
            for k in (
                "autoAccepted",
                "manualPending",
                "rejected",
                "totalRows",
                "acceptanceGateMet",
            )
        }
        live["matrix"] = settlement_matrix_status()
        audit = audit_gold_payment_pipeline()
        live["gold"] = {
            k: audit.get(k)
            for k in ("gapCode", "paymentLines", "treatmentEstimates", "rootCause", "newestPaymentCsv")
        }
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
        ("MOONSHOT_APPLIED_HAL10605_GOLD_SETTLEMENT_MATRIX_2026-07-13.md", 3500),
        ("MOONSHOT_DENTAL_INSURANCE_INDUSTRY_KNOWLEDGE_2026-07-13.md", 4000),
        ("MOONSHOT_APPLIED_HAL10604_MOONSHOT_INDUSTRY_ALIAS_2026-07-13.md", 2000),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    live = _live_snapshot()
    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Confirm HAL-10605 apply. Pick THE single best NEXT package. CONSULT ONLY.\n\n"
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
        headers["X-Title"] = "NR2 Whats Next After HAL-10605"
    print("Calling Moonshot AI (whats next after 10605 — consult only)...")

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
        try:
            if isinstance(exc, urllib.error.HTTPError) and exc.fp is not None:
                body = exc.read().decode("utf-8", errors="replace")
                raw = {"error": content, "body": body}
                content = f"{content}\n{body}"
        except Exception:
            pass

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (OUT / f"moonshot_whats_next_after_hal10605_{stamp}.json").write_text(
        json.dumps(raw, indent=2), encoding="utf-8"
    )

    header = (
        f"# Moonshot AI — What's Next After HAL-10605 "
        f"(CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** hal-10605  \n"
        f"**Prior apply:** HAL-10605 (`99b17ef`)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_hal10605_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves (`proceed`).\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_HAL10605_{DATE}.md"
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_HAL10605_{DATE}.md"
    doc.write_text(full, encoding="utf-8")
    out.write_text(full, encoding="utf-8")
    print(doc)
    print(out)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
