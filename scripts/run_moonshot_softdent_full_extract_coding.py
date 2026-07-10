"""Moonshot AI — SoftDent FULL data retrieval coding (every domain + transactions).

Operator request is passed VERBATIM. Ask Moonshot for paste-ready coding + findings.
Does NOT apply code into the live app — report only unless operator later says proceed.
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
ask moonshot ai for the coding to retrieve all data from softdent, report his findings.  and i mean every piece of data.  even transactions.
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — SoftDent / Carestream Sensei data-integration engineer
for NewRidge Financial 2.0 (NR2), a local HTTPS Apex app for a Kansas dental S-corp.

CRITICAL MISSION:
The operator wants CODING to retrieve ALL SoftDent data — every piece — INCLUDING TRANSACTIONS.
Do not soft-pedal scope. Inventory every domain. Provide paste-ready code / SQL / PowerShell /
Python that NR2 can use. Report findings honestly against LIVE FACTS in the user context.

ANSWER ALL OF:
(A) Complete SoftDent data inventory — every domain that exists in SoftDent / Sensei / exports
    (patients, providers, appointments, operatory, procedures, ADA fees, clinical notes,
     treatment plans, hygiene recall, case acceptance, claims, claim status, insurance/payers,
     A/R aging, patient ledger, payments, adjustments/write-offs, daysheet, register,
     TRANSACTIONS (line-level), production by provider/ADA, collections, payment plans,
     documents/attachments metadata if available, anything else SoftDent stores).
(B) For EACH domain: best extraction lane (Sensei DataSync JSON / ODBC SQL / automated
    SoftDentFinancialExports JSONL / SoftDent Report CSV / Register-for-Period / manual).
(C) Paste-ready CODING: Python extract functions, ODBC SELECT templates, JSONL parsers
    (especially transactions_for_period.jsonl + register_for_period.jsonl), schema for
    sd_* / analytics tables, env vars, discovery script extensions, sync orchestration.
(D) Explicit TRANSACTIONS section — how to pull every transaction row, map fields, store,
    and prove completeness (row counts, date ranges, checksums vs daysheet totals).
(E) Gaps vs current NR2 (what already works, what's empty, what's missing code).
(F) Ranked implementation plan MUST / SHOULD / NICE with acceptance tests.
(G) PHI / consent / read-only safety — never invent dollars; no writeback unless gated.

CONSTRAINTS:
1. Use LIVE FACTS as ground truth for what is already on disk / in DB today.
2. SoftDent SQL schema is NOT public — discovery-first for ODBC; do not invent table names
   as if verified. Mark illustrative SQL clearly; prefer extending
   discover_softdent_odbc_schema.py + suggestedEnv.
3. Prefer extending existing NR2 modules (softdent_odbc_extract.py, softdent_operational_pipeline.py,
   softdent_practice_exports.py, import_sync.py) over greenfield rewrites.
4. Provide paste-ready code blocks labeled by file path. This is a CODING + FINDINGS report.
   Cursor will NOT apply until operator says proceed — but YOU must still deliver the code.
5. Build reviewed: hal-10350.

OUTPUT FORMAT (strict markdown):
# Verdict
## 0. Operator Intent (quote verbatim)
## 1. Findings — What SoftDent Data Exists vs What NR2 Already Has
Inventory table: Domain | SoftDent source | NR2 status today | Gap
## 2. Extraction Lanes Ranked (best → fallback) for FULL coverage
## 3. TRANSACTIONS — Complete Retrieval Coding (mandatory deep section)
Field map, parsers, SQL/ODBC if applicable, storage, completeness proofs.
## 4. Paste-Ready Coding Pack (every other domain)
Organized by file; include ODBC discovery extensions, JSONL parsers, sync hooks.
## 5. Full Domain Checklist (checkbox-style — nothing omitted)
## 6. Implementation Phases + Acceptance Tests
## 7. Risks, PHI, Consent, Rollback
## 8. Operator Next Actions (concrete)
"""


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 20),
    ("NewRidgeFinancial2/docs/MOONSHOT_SOFTDENT_EXTRACT_REPORT_2026-07-08.md", 120),
    ("NewRidgeFinancial2/docs/MOONSHOT_PHASEF_ODBC_RUNBOOK.md", 80),
    ("NewRidgeFinancial2/scripts/discover_softdent_odbc_schema.py", 100),
]


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} lines truncated]"


def _excerpt_python(path: Path, marker: str, label: str, max_lines: int = 60) -> str:
    if not path.is_file():
        return f"### EXCERPT: {label}\n(missing)"
    text = path.read_text(encoding="utf-8", errors="replace")
    idx = text.find(marker)
    if idx < 0:
        return f"### EXCERPT: {label}\n(marker missing)"
    chunk = text[idx : idx + 5000]
    return f"### EXCERPT: {path.name}::{label}\n```python\n{_truncate(chunk, max_lines)}\n```"


def build_context() -> str:
    parts: list[str] = []
    for rel, max_lines in CONTEXT_FILES:
        path = REPO / rel
        if not path.is_file():
            parts.append(f"### FILE: {rel}\n(missing)")
            continue
        body = _truncate(path.read_text(encoding="utf-8", errors="replace"), max_lines)
        ext = path.suffix.lstrip(".") or "txt"
        parts.append(f"### FILE: {rel}\n```{ext}\n{body}\n```")

    odbc = REPO / "NewRidgeFinancial2" / "softdent_odbc_extract.py"
    for marker, label, n in (
        ("SD_TABLES = (", "SD_TABLES + ODBC_QUERY_ENV", 50),
        ("def extract_softdent_odbc", "extract_softdent_odbc", 80),
        ("def _populate_from_daysheet", "_populate_from_daysheet", 60),
        ("def ensure_sd_schema", "ensure_sd_schema", 50),
    ):
        parts.append(_excerpt_python(odbc, marker, label, n))

    pipeline = REPO / "NewRidgeFinancial2" / "softdent_operational_pipeline.py"
    for marker, label, n in (
        ("INSURANCE_PAYMENT_CODES", "payment/writeoff codes", 40),
        ("def _load_daysheet_transactions", "_load_daysheet_transactions", 50),
    ):
        parts.append(_excerpt_python(pipeline, marker, label, n))

    parts.append(
        """### LIVE FACTS (captured 2026-07-10 for this consult — ground truth)
- Build: **hal-10350**
- Primary export lane LIVE and refreshing today: `C:\\SoftDentFinancialExports`
  - `daysheet.jsonl` (~17 KB, refreshed 2026-07-10 09:50)
  - `transactions_for_period.jsonl` (~842 KB, refreshed 2026-07-10 09:50) — TRANSACTIONS PRESENT ON DISK
  - `register_for_period.jsonl` (~8 KB, refreshed 2026-07-10 09:50)
  - `account_aging.jsonl`, `writeoff_totals.jsonl` refreshed same time
  - `operatory_schedule.json` present (~1.5 KB, refreshed 2026-07-10 09:54)
- Analytics DB LIVE counts (2026-07-10 query of softdent_financial_analytics.db):
  - transactions: **1226** (PRESENT)
  - financial_rows: 1317
  - production_by_ada: 2827; production_by_provider: 265
  - daysheet_totals: 3; account_aging: 1; writeoff_totals: 10
  - sd_patients: **11969**; sd_appointments: **10868**; sd_procedures: **25757**
  - sd_providers: 42; sd_claims: 60; sd_payments: **22**; sd_adjustments: **13**
  - EMPTY still: insurance_claims, outstanding_claims, claims_outstanding, collection_summary,
    treatment_plan_summary, fee_schedules, payment_plans, provider_reference,
    insurance_company_reference, transaction_code_reference, adjustments (non-sd), etc.
- Sensei DataSync lane appears ACTIVE (sd_patients/appointments/procedures in thousands)
- ODBC DSN may still be unset — Sensei JSON path is carrying deep patient/appt/proc data
- NO dedicated sd_transactions table; line transactions live in analytics `transactions`
  + `transactions_for_period.jsonl` (~842 KB on disk today)
- import_sync already pulls SoftDentFinancialExports; ensure_softdent_odbc_fresh on sync
- Operator wants EVERY piece of SoftDent data out — including transactions — and wants CODING
- PHI stays local; read-only preferred; consent gate for ODBC extract admin API
"""
    )
    return "\n\n".join(parts)


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
        "Deliver CODING + FINDINGS for retrieving ALL SoftDent data, especially TRANSACTIONS.\n"
        "Paste-ready code required. Cursor will report findings; do not assume code is applied yet.\n\n"
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
        "max_tokens": 20000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 SoftDent Full Extract Coding"

    print("Calling Moonshot AI (full SoftDent extract coding + findings)...")
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
        f"# Moonshot AI — SoftDent FULL Data Retrieval Coding + Findings\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10350  \n"
        f"**Script:** `scripts/run_moonshot_softdent_full_extract_coding.py`  \n"
        f"**Apply:** Report only until operator says proceed.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_SOFTDENT_FULL_EXTRACT_CODING_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_SOFTDENT_FULL_EXTRACT_CODING_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
