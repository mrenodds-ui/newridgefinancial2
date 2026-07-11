"""Moonshot AI — SoftDent charge→insurance paid→ADA code for HAL treatment planning.

Operator request passed VERBATIM. CONSULT / REPORT ONLY — do not apply code.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
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

OPERATOR_REQUEST_VERBATIM = """
ask moonshot ai about softdent.  ask him if he can pull transactions off patients' list from charges to what insurance paid for those transactions and then tie it back to the insuance company to figure how much they paid for ada dental claim code after write off so we can teach hal how to do treatment planning.
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — SoftDent / Carestream dental RCM + treatment-planning
data architect for NewRidge Financial 2.0 (NR2) / HAL.

CRITICAL QUESTION:
Can SoftDent (via NR2's existing lanes or additional SoftDent reports/ODBC) pull a patient's
transaction list from **charges → insurance payments → write-offs/adjustments**, then join
back to the **insurance company** and compute **how much each ADA/CDT code paid after write-off**,
so HAL can learn realistic treatment-planning estimates (expected insurance portion vs patient portion)?

Answer honestly with YES / PARTIAL / NO using LIVE FACTS as ground truth.
Do not invent that payer/ADA/claim join fields exist if LIVE FACTS show them empty or mis-mapped.
Do not invent dollar amounts or patient rows.
CONSULT ONLY — no production code apply. Paste-ready exploratory SQL/report names OK.

Cover:
(A) SoftDent conceptual model: charge / payment / adjustment / claim / InsCo / ADA(CDT) / write-off.
(B) What NR2 already has vs what is missing for the exact join the operator wants.
(C) Why current transactions_for_period is insufficient (code-as-dollar, empty payer/claim).
(D) Best SoftDent report / ODBC / Sensei / ERA paths ranked MUST / SHOULD / NICE to get:
    charge fee, write-off/CO-45, insurance paid, patient balance, InsCo name, ADA/CDT code.
(E) How to teach HAL once data exists (learned_memories vs analytics aggregates — no PHI in memory).
(F) Treatment-planning honesty rules: estimates vs guarantees; never invent allowed amounts.
(G) Operator next actions (which SoftDent reports to export, where to drop files, what HAL can say today).

OUTPUT FORMAT (strict markdown):
# Verdict (YES | PARTIAL | NO)
## 0. Operator Intent (quote verbatim)
## 1. SoftDent Data Model for Charge → Paid → Payer → ADA
## 2. What NR2 Has Today (live evidence)
## 3. Gap Analysis (why the join fails today)
## 4. Feasible Paths Ranked (MUST / SHOULD / NICE)
## 5. How HAL Should Learn Treatment Planning (once data exists)
## 6. Risks / PHI / Honesty
## 7. Operator Next Actions
"""


def build_context() -> str:
    return """
### LIVE FACTS — SoftDent / NR2 (captured 2026-07-10)

**Build:** hal-10390 (transaction extract applied at hal-10370).

**Working lanes (do NOT recommend parsing live C:\\softdent *.dat):**
1. `C:\\SoftDentFinancialExports\\transactions_for_period.jsonl` → `sd_transactions_full` (1284 rows, parity 1.0)
2. Sensei DataSync → `sd_patients` 11969 · `sd_appointments` 10868 · `sd_procedures` 25757
3. SoftDent report CSV / claims imports → `sd_claims` 61
4. Optional ODBC discovery exists in code; insurance_* analytics tables exist but are **empty (0 rows)**
5. Prior Moonshot DAT/sys consult: NO direct `.dat` read (no system.sys / DDFs)

**`sd_transactions_full` live shape (1284 rows):**
- Types: transaction 1048 · payment 164 · adjustment 72
- Fields present in JSONL: transaction_date, posting_date, service_date, transaction_code,
  transaction_description, transaction_type, amount, provider_id/name, collecting_provider_id,
  patient_id, account_id, guarantor_id
- **payer nonempty: 0** · **claim_id nonempty: 0**
- patient_id nonempty: 1001/1284
- `transaction_code` is often a **dollar-like string** (e.g. "56.00", "305.00", "212.96") — NOT ADA D-codes
- Extract maps that code into `ada_code` column → polluted values like 137, 100, 11.93 (not CDT)
- Schema columns for payer / claim_id / original_transaction_id exist but are unused by this export

**`sd_payments`:** 164 rows · **payer nonempty: 0**
**`sd_adjustments`:** 86 rows · codes from transaction extract (not InsCo-linked)
**`sd_claims`:** 61 rows · payer filled 61/61 but almost all generic **"Insurance"** (60) + 1 "Delta Dental"
**`sd_procedures` (Sensei):** 25757 rows with patient_id + ada_code + production —
  codes look SoftDent-internal with trailing zeros (12000, 111000, 275000…) not canonical D0120/D1110/D2750;
  production present; **no insurance paid / write-off / InsCo on this table**

**Empty SoftDent financial importer tables (schema ready, 0 rows — ideal for this ask if exported):**
- insurance_payment_distribution
- insurance_check_distribution
- insurance_income
- insurance_claims / claims_outstanding / outstanding_claims
- insurance_company_reference
- fee_schedules
- unsubmitted_claims

**HAL learning policy (already governed):**
- Staff: `Remember this: …` → `app_data/nr2/learned_memories.jsonl` (no PHI/secrets)
- Maintainer: `docs/hal_knowledge/memories.jsonl`
- Runtime dollars must come from imports — HAL must not invent allowed amounts or payer pays

**Operator goal:**
Teach HAL treatment planning using real historical: charge → write-off → insurance paid by InsCo by ADA/CDT.

### Operator ask
Answer whether SoftDent/NR2 can pull patient transactions from charges through insurance paid,
tie to insurance company, and compute ADA-code paid-after-write-off for HAL treatment planning.
"""


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No Moonshot/OpenRouter API key.", file=sys.stderr)
        return 1

    if "moonshot" in (base_url or "").lower():
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    else:
        model = str(
            os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2"
        ).strip()

    print(f"Using {key_name} @ {base_url} model={model}")
    user = (
        "OPERATOR REQUEST (VERBATIM — do not rewrite):\n\n"
        f"{OPERATOR_REQUEST_VERBATIM}\n\n"
        "CONSULT / REPORT ONLY. Answer YES / PARTIAL / NO with evidence from LIVE FACTS.\n\n"
        "## Context\n\n"
        + build_context()
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 12000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 SoftDent Charge-Payer-ADA Treatment Planning"

    print("Calling Moonshot AI (SoftDent charge->payer->ADA treatment planning)...")
    req = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3600) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = extract_message_content(body)
        status = "ok"
    except urllib.error.HTTPError as exc:
        content = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:4000]}"
        status = f"HTTP {exc.code}"
    except Exception as exc:
        content = str(exc)
        status = "error"

    header = (
        f"# Moonshot AI — SoftDent Charge → Insurance Paid → ADA for HAL Treatment Planning\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10390  \n"
        f"**Script:** `scripts/run_moonshot_softdent_ada_payer_tx_consult.py`  \n"
        f"**Apply:** Report only — do not code until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_SOFTDENT_ADA_PAYER_TX_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_SOFTDENT_ADA_PAYER_TX_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
