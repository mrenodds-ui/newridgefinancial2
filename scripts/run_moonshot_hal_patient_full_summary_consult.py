"""Moonshot AI — HAL one-patient mega-summary (data + tx + notes + claims).

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
ask moonoshot ai how to program hal to give a summary of patient's data and transactional information as well as their treatment notes, claims, everything in one summary.
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — senior NR2 Apex + HAL architect for
NewRidge Family Financial (Kansas dental S-corp; SoftDent + QuickBooks imports;
local Ollama single 24B on R9700; HAL tools on HTTPS loopback).

CRITICAL CONSTRAINTS:
1. Answer the OPERATOR REQUEST VERBATIM: how to program HAL to produce ONE summary
   covering patient data, transactional information, treatment notes, claims —
   "everything in one summary."
2. CONSULT ONLY — DO NOT APPLY code. DO NOT invent product diffs as already shipped.
   Wait for operator approve / proceed.
3. SoftDent is READ-ONLY forever — never write back. Never invent dollars.
   empty ≠ $0 (missing estimate / balance / fee must stay empty or "unknown", not $0).
4. PHI is LOCAL-ONLY. "Everything in one summary" MUST mean:
   a local SoftDent-derived patient dossier assembled via HAL tools on loopback,
   staff-gated + audited — NOT a cloud dump, NOT SoftDent write, NOT pasting full
   charts into OpenAI/Moonshot prompts in production. Cloud models stay off by default.
5. Ground in EXISTING HAL tools and stores. Prefer composing / orchestrating:
   read_clinical_summary, draft_insurance_narrative, lookup_treatment_estimate,
   read_claims_summary, join_claim_payers, lookup_fee_schedule, list_eligibility_cache,
   softdent_extract_status, and related loopback APIs — plus softdent stores
   (sd_patients, sd_claims, sd_procedures, sd_appointments), clinical note imports,
   treatment planning (softdent_treatment_planning), claims workbench / OM widgets.
   Propose a NEW orchestrator tool (e.g. summarize_patient_dossier) only if composition
   of existing tools is insufficient; justify it.
6. Overlap with OM Mon–Thu / HAL patient-access consult is welcome: include a short
   "HAL patient access" subsection so this consult stands alone if needed.
7. Rank MUST / SHOULD / NICE. Coding plan with concrete files. End with APPROVAL CHECKLIST.

OUTPUT FORMAT (strict markdown):
# Verdict — HAL one-patient mega-summary (dossier)
## 0. Operator Intent (quote; consult-only)
## 1. Current State Audit (HAL tools, SoftDent stores, clinical notes, claims, tx planning)
## 2. Gap Map
Table: Area | Status | Gap | Effort | Depends on
## 3. Target Design — "everything in one summary"
### 3A Meaning of mega-summary (sections, honesty rules, what is excluded)
### 3B Tool/API orchestration (existing tools vs new summarize_patient_dossier)
### 3C UX sketch (HAL chat utterance → gated fetch → structured reply; optional OM dossier)
### 3D Staff gate + audit trail (who can ask, what is logged, PHI display)
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
    ("NewRidgeFinancial2/docs/architecture.md", 30),
    ("NewRidgeFinancial2/docs/MOONSHOT_OM_MON_THU_PATIENTS_HAL_CONSULT_2026-07-11.md", 80),
    ("NewRidgeFinancial2/docs/MOONSHOT_OM_TX_CLAIMS_SCHEDULE_APPLIED_2026-07-11.md", 40),
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
    agent = nr2 / "site" / "hal-agent.js"
    if agent.is_file():
        text = agent.read_text(encoding="utf-8", errors="replace")
        keys = []
        for k in (
            "read_clinical_summary",
            "draft_insurance_narrative",
            "lookup_treatment_estimate",
            "lookup_fee_schedule",
            "join_claim_payers",
            "read_claims_summary",
            "softdent_extract_status",
            "list_eligibility_cache",
            "fetch_eligibility_271",
            "build_collections_queue",
            "predict_claim_denial_risk",
            "build_appeal_packet",
            "read_program_snapshot",
            "read_current_context",
        ):
            if k in text:
                keys.append(k)
        parts.append("### LIVE: HAL tools present in hal-agent.js\n" + ", ".join(keys))
        parts.append(
            "### EXTRACT: hal-agent.js — read_clinical_summary\n```javascript\n"
            + _extract_lines(agent, "read_clinical_summary: {", "build_collections_queue: {", 35)
            + "\n```"
        )
        parts.append(
            "### EXTRACT: hal-agent.js — draft_insurance_narrative (head)\n```javascript\n"
            + _extract_lines(agent, "draft_insurance_narrative: {", "read_clinical_summary: {", 40)
            + "\n```"
        )
        parts.append(
            "### EXTRACT: hal-agent.js — lookup_treatment_estimate\n```javascript\n"
            + _extract_lines(agent, "lookup_treatment_estimate: {", "list_eligibility_cache: {", 30)
            + "\n```"
        )

    parts.append(
        "### EXTRACT: softdent_treatment_planning.py — head + HAL_TOOLS\n```python\n"
        + _truncate(
            (nr2 / "softdent_treatment_planning.py").read_text(encoding="utf-8", errors="replace")
            if (nr2 / "softdent_treatment_planning.py").is_file()
            else "(missing)",
            45,
        )
        + "\n```"
    )
    parts.append(
        "### EXTRACT: softdent_odbc_extract.py — sd_patients / sd_claims schema hints\n```python\n"
        + _extract_lines(
            nr2 / "softdent_odbc_extract.py",
            "CREATE TABLE IF NOT EXISTS sd_patients",
            None,
            35,
        )
        + "\n```"
    )
    parts.append(
        "### EXTRACT: softdent_odbc_extract.py — sd_claims\n```python\n"
        + _extract_lines(
            nr2 / "softdent_odbc_extract.py",
            "CREATE TABLE IF NOT EXISTS sd_claims",
            None,
            30,
        )
        + "\n```"
    )

    parts.append(
        """### LIVE FACTS
- SoftDent READ-ONLY forever. Never invent dollars. empty ≠ $0.
- PHI local-only; production HAL uses local 24B on loopback; cloud off by default.
- HAL already has discrete tools: read_clinical_summary, draft_insurance_narrative,
  lookup_treatment_estimate, read_claims_summary, join_claim_payers, lookup_fee_schedule,
  list_eligibility_cache, softdent_extract_status — but NO single "summarize everything
  about this patient" orchestrator yet.
- read_clinical_summary → DesktopBridge.fetchClinicalContext (limit 5; patientId optional).
- lookup_treatment_estimate → payer × ADA SoftDent-derived estimate (empty ≠ $0).
- Claims narrative / workbench + OM widgets exist; patient dossier API may be proposed
  in prior Mon–Thu consult (om_patient_dossier / get_patient_dossier) — not applied yet
  unless operator approved.
- Operator wants ONE HAL summary: patient data + transactional info + treatment notes
  + claims + "everything" — interpret as staff-gated local dossier summary, not cloud dump.
- Prefer compose-then-summarize on loopback over sending raw PHI to Moonshot/OpenAI.
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
        "CONSULT ONLY — recommend how to program HAL for one local SoftDent-derived "
        "patient mega-summary (data + transactional + treatment notes + claims). "
        "Do not apply. SoftDent READ-ONLY; empty ≠ $0; PHI staff-gated + audited on loopback.\n\n"
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
        headers["X-Title"] = "NR2 HAL Patient Full Summary Consult"

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
        f"# Moonshot AI — HAL Patient Full Summary / Mega-Dossier (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Script:** `scripts/run_moonshot_hal_patient_full_summary_consult.py`  \n"
        f"**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_HAL_PATIENT_FULL_SUMMARY_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_HAL_PATIENT_FULL_SUMMARY_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
