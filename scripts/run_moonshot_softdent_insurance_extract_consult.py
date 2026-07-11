"""Moonshot AI — SoftDent insurance extract for dossier Availity auto-eligibility.

CONSULT ONLY. Operator request VERBATIM. Await approval before applying code.
"""

from __future__ import annotations

import json
import os
import sys
import time
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
ask moonshot ai how to extract SoftDent patient insurance fields (member id,
subscriber id, payer id / carrier name) into the local SoftDent SQLite extract
so HAL patient dossier eligibility can auto-resolve Availity Coverages without
staff manually typing memberId/payerId every time
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — senior NR2 Apex + HAL architect for
NewRidge Family Financial (Kansas dental S-corp; SoftDent + QuickBooks imports;
local Ollama single 24B on R9700; HAL tools on HTTPS loopback).

CRITICAL CONSTRAINTS:
1. Answer the OPERATOR REQUEST VERBATIM: how to **extract SoftDent patient
   insurance fields** into local SQLite so dossier Availity eligibility can
   auto-resolve (memberId / payerId / carrier) without manual overrides.
2. CONSULT ONLY — DO NOT APPLY code. Wait for operator approve / proceed.
3. SoftDent is READ-ONLY forever (SELECT / ODBC / CSV only). Never invent dollars.
   empty ≠ $0. gaps ≠ invent member IDs.
4. PHI is LOCAL-ONLY. Audit hashes patient ids. Do not ship raw member IDs to cloud.
5. Ground in EXISTING code (hal-10497 already ships dossier.eligibility):
   - softdent_odbc_extract.py ensure_sd_schema — today has sd_patients, claims,
     payments, etc. **NO sd_patient_insurance table in schema yet**
   - patient_dossier._resolve_eligibility_for_patient already reads
     sd_patient_insurance IF present (PRAGMA defensive); otherwise gaps
   - clearinghouse / Availity Coverages + eligibility_cache_store
   - NR2_PROVIDER_NPI practice-level; DOSSIER_ELIGIBILITY_ENABLED
   - CSV SoftDentFinancialExports paths already used for insurance payments
6. Prefer extend softdent_odbc_extract + optional CSV ingest over new vendors.
   Rank MUST / SHOULD / NICE. Coding plan with concrete files. APPROVAL CHECKLIST.

OUTPUT FORMAT (strict markdown):
# Verdict — SoftDent insurance extract for dossier Availity auto-eligibility
## 0. Operator Intent (quote; consult-only)
## 1. Current State Audit (ODBC extract schema vs dossier resolver vs Availity)
## 2. Gap Map
Table: Area | Status | Gap | Effort | Depends on
## 3. Target Design
### 3A sd_patient_insurance schema (columns; PRIMARY KEY; empty≠invent)
### 3B Extract sources (ODBC SoftDent tables/views OR CSV export) — honest discovery
### 3C Wire into ensure_sd_schema + extract job + dossier (already reads table)
### 3D PHI, redaction, audit, demo vs live honesty
## 4. Coding Plan by Phase (files · paste-ready sketches · validation)
## 5. MUST / SHOULD / NICE ranked table
## 6. Risks, PHI, SoftDent honesty, Rollback
## 7. Approval Checklist
DO NOT APPLY until operator says approve / proceed.
"""


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} lines truncated]"


def _extract_lines(path: Path, start_marker: str, end_marker: str | None, max_lines: int) -> str:
    if not path.is_file():
        return "(missing)"
    text = path.read_text(encoding="utf-8", errors="replace")
    start = text.find(start_marker)
    if start < 0:
        return f"(marker not found: {start_marker[:80]})"
    if end_marker:
        end = text.find(end_marker, start + len(start_marker))
        chunk = text[start : (end if end > start else start + 14000)]
    else:
        chunk = text[start : start + 14000]
    return _truncate(chunk, max_lines)


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 12),
    ("NewRidgeFinancial2/docs/MOONSHOT_AVAILITY_DOSSIER_ELIGIBILITY_APPLIED_2026-07-11.md", 60),
    ("NewRidgeFinancial2/docs/MOONSHOT_AVAILITY_DOSSIER_ELIGIBILITY_CONSULT_2026-07-11.md", 80),
]


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

    nr2 = REPO / "NewRidgeFinancial2"
    parts.append(
        "### EXTRACT: softdent_odbc_extract.py — ensure_sd_schema\n```python\n"
        + _extract_lines(nr2 / "softdent_odbc_extract.py", "def ensure_sd_schema", None, 90)
        + "\n```"
    )
    parts.append(
        "### EXTRACT: softdent_odbc_extract.py — table env keys\n```python\n"
        + _extract_lines(nr2 / "softdent_odbc_extract.py", "SD_TABLES", None, 40)
        + "\n```"
    )
    parts.append(
        "### EXTRACT: patient_dossier.py — eligibility resolver\n```python\n"
        + _extract_lines(
            nr2 / "patient_dossier.py",
            "def _resolve_eligibility_for_patient",
            "def build_patient_dossier",
            120,
        )
        + "\n```"
    )
    parts.append(
        """### LIVE FACTS
- SoftDent READ-ONLY forever. Never invent dollars or member IDs.
- ensure_sd_schema today: sd_patients, sd_providers, sd_procedures, sd_appointments,
  sd_claims, sd_payments, sd_adjustments, sd_extract_meta — NO insurance table.
- hal-10497 dossier.eligibility already PRAGMA-reads sd_patient_insurance if present;
  otherwise gaps: memberId, payerId, providerNPI.
- Availity Coverages wired; demo until Standard Plan; NR2_PROVIDER_NPI practice-level.
- Operator wants SoftDent → SQLite insurance fields so auto Availity works without
  typing memberId/payerId each time.
- Prefer ODBC SELECT discovery + optional CSV SoftDentFinancialExports path.
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
        "CONSULT ONLY — recommend SoftDent insurance extract into local SQLite for "
        "dossier Availity auto-eligibility. Do not apply. SoftDent READ-ONLY; "
        "empty ≠ $0; gaps ≠ invent; PHI local.\n\n"
        "## Codebase context\n\n"
        + build_context()
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 14000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 SoftDent Insurance Extract Consult"

    print("Calling Moonshot AI (consult only — will not apply)...")
    req = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    content = ""
    status = "error"
    last_err = ""
    for attempt in range(1, 5):
        try:
            with urllib.request.urlopen(req, timeout=3600) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            content = extract_message_content(body)
            status = "ok"
            break
        except urllib.error.HTTPError as exc:
            content = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:4000]}"
            status = f"HTTP {exc.code}"
            break
        except Exception as exc:
            last_err = str(exc)
            content = last_err
            status = "error"
            print(f"Attempt {attempt}/4 failed: {last_err}", file=sys.stderr)
            if attempt < 4:
                time.sleep(5 * attempt)

    header = (
        f"# Moonshot AI — SoftDent Insurance Extract for Dossier Availity (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Script:** `scripts/run_moonshot_softdent_insurance_extract_consult.py`  \n"
        f"**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_SOFTDENT_INSURANCE_EXTRACT_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_SOFTDENT_INSURANCE_EXTRACT_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
