"""Moonshot AI — OM Mon–Thu schedule list + expand tx/clinical/claims + HAL patient access.

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
ask moonshot how to program and code in the ofice manager page a list of patients sheduled from Monday to Thurdays and how to display them in a widget with information.  Also how to expland treatment planning, patient information clindical notes and claim reviews.  also how hal has total access to a patients data such as insurance clincial notes if we asked him about a patient
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — senior NR2 Apex + HAL architect for
NewRidge Family Financial (Kansas dental S-corp; SoftDent + QuickBooks imports;
local Ollama single 24B on R9700).

CRITICAL CONSTRAINTS:
1. Answer the OPERATOR REQUEST VERBATIM. Cover ALL of:
   A) Program/code Office Manager: list patients scheduled Monday–Thursday in a widget with useful info
   B) Expand treatment planning, patient information, clinical notes, and claim reviews
   C) How HAL can answer about a specific patient with insurance + clinical notes access
2. CONSULT ONLY — DO NOT APPLY code. Wait for approve.
3. SoftDent is READ-ONLY forever — never write back. Never invent dollars. empty ≠ $0.
4. PHI is LOCAL-ONLY. Cloud/OpenAI stays off by default; if ever used, sanitize PHI.
   "Total access" MUST mean: local SoftDent-derived stores + HAL tools on loopback —
   NOT unrestricted cloud export, NOT SoftDent write, NOT dumping full charts into widgets.
   Prefer: staff-gated patient lookup by id/name with audit; widgets show initials/hash by default;
   HAL tools fetch full local context only when staff asks about that patient.
5. Ground in LIVE FACTS. Reuse: nr2_softdent_daily, sd_appointments/sd_patients/sd_claims,
   softdent_treatment_planning, clinical note imports, claims/narrative packs, hal-agent tools
   (read_clinical_summary, draft_insurance_narrative, lookup_treatment_estimate, etc.).
6. OM-A0 (hal-10494) already loads TODAY's appointments. This ask expands to Mon–Thu list widget.
7. Rank MUST / SHOULD / NICE. End with APPROVAL CHECKLIST.

OUTPUT FORMAT (strict markdown):
# Verdict — OM Mon–Thu schedule + expanded patient surfaces + HAL patient access
## 0. Operator Intent (quote; consult-only)
## 1. Current State Audit (OM schedule, tx planning, clinical notes, claims, HAL tools)
## 2. Gap Map
Table: Area | Status | Gap | Effort | Depends on
## 3. Target Design
### 3A OM Mon–Thu scheduled patients widget (fields, PHI display rules)
### 3B Expand treatment planning / patient info / clinical notes / claim reviews
### 3C HAL patient dossier access model (tools, consent, audit, what HAL may/may not say)
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
    ("NewRidgeFinancial2/docs/MOONSHOT_OM_TX_CLAIMS_SCHEDULE_APPLIED_2026-07-11.md", 50),
    ("NewRidgeFinancial2/docs/architecture.md", 30),
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
        "### EXTRACT: nr2_softdent_daily.py — appointments_today + hash\n```python\n"
        + _extract_lines(nr2 / "nr2_softdent_daily.py", "def _hash_patient_id", "def claims_outstanding", 90)
        + "\n```"
    )
    parts.append(
        "### EXTRACT: apex_missing_widgets_pack.py — OM board / claims queue\n```python\n"
        + _extract_lines(
            nr2 / "apex_missing_widgets_pack.py",
            "def build_operatory_board",
            "def append_financial_missing",
            80,
        )
        + "\n```"
    )
    parts.append(
        "### EXTRACT: softdent_odbc_extract.py — sd_appointments / sd_patients schema\n```python\n"
        + _extract_lines(nr2 / "softdent_odbc_extract.py", "CREATE TABLE IF NOT EXISTS sd_appointments", None, 40)
        + "\n```"
    )
    parts.append(
        "### EXTRACT: softdent_treatment_planning.py — head + HAL_TOOLS\n```python\n"
        + _truncate(
            (nr2 / "softdent_treatment_planning.py").read_text(encoding="utf-8", errors="replace")
            if (nr2 / "softdent_treatment_planning.py").is_file()
            else "(missing)",
            40,
        )
        + "\n```"
    )

    # HAL tool names related to patient/clinical/claims
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
        ):
            if k in text:
                keys.append(k)
        parts.append("### LIVE: HAL tools present in hal-agent.js\n" + ", ".join(keys))

    parts.append(
        """### LIVE FACTS
- Build tip: hal-10494. SoftDent READ-ONLY. Local AI: single 24B. Cloud off by default.
- OM already loads TODAY appointments via appointments_today_snapshot + operatory board.
- sd_appointments columns: practice_id, patient_id, appt_date, provider_code, status (NO operatory/time cols).
- sd_patients, sd_claims, sd_procedures exist in analytics SQLite.
- Treatment planning: softdent_treatment_planning + HAL lookup_treatment_estimate tool.
- Clinical notes: SoftDent import / narrative packs; HAL read_clinical_summary exists.
- Claims: workbench + OM claims-narrative-queue + draft_insurance_narrative.
- PHI: OM live board uses 4-char patient hashes by default.
- Operator wants Mon–Thu scheduled patient LIST widget with information (richer than today-only board).
- Operator wants HAL "total access" to patient insurance + clinical notes when asking about a patient —
  interpret as local dossier tools with staff query + audit, NOT cloud dump / SoftDent write.
- Ops note: weekday SoftDent has appointments; Saturdays may be empty (honest).
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
        "CONSULT ONLY — recommend coding for OM Mon–Thu patient list widget, expanded "
        "treatment/patient/clinical/claims surfaces, and HAL local patient dossier access. "
        "Do not apply.\n\n"
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
        headers["X-Title"] = "NR2 OM Mon-Thu Patients HAL Consult"

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
    for attempt in range(1, 4):
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
            print(f"Attempt {attempt}/3 failed: {last_err}", file=sys.stderr)
            if attempt < 3:
                time.sleep(5 * attempt)

    header = (
        f"# Moonshot AI — OM Mon–Thu Patients + Expanded Surfaces + HAL Patient Access (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Script:** `scripts/run_moonshot_om_mon_thu_patients_hal_consult.py`  \n"
        f"**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_OM_MON_THU_PATIENTS_HAL_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_OM_MON_THU_PATIENTS_HAL_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
