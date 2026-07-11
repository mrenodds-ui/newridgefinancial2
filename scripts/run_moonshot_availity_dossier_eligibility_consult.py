"""Moonshot AI — Availity eligibility into HAL patient dossier.

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
ask moonshot ai how to put Availity eligibility (benefits, deductibles, coverages)
into the HAL patient dossier so staff can capture dental patient insurance from
SoftDent patient context via Availity Coverages API (demo until Standard Plan live)
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — senior NR2 Apex + HAL architect for
NewRidge Family Financial (Kansas dental S-corp; SoftDent + QuickBooks imports;
local Ollama single 24B on R9700; HAL tools on HTTPS loopback).

CRITICAL CONSTRAINTS:
1. Answer the OPERATOR REQUEST VERBATIM: how to wire **Availity eligibility**
   (benefits / deductibles / coverages 270→271) into the **HAL patient dossier**.
2. CONSULT ONLY — DO NOT APPLY code. DO NOT invent product diffs as already shipped.
   Wait for operator approve / proceed.
3. SoftDent is READ-ONLY forever. Never invent dollars. empty ≠ $0.
4. PHI is LOCAL-ONLY. Audit must hash patient ids. Do not recommend cloud PHI dumps.
5. Ground in EXISTING code:
   - patient_dossier.py / om_patient_dossier.py / patient_dossier_prompts.py
   - GET /api/apex/patient-dossier/{id} + summarize_patient_dossier
   - clearinghouse_eligibility_adapter.py + clearinghouse_live_clients.fetch_availity_271
   - map_availity_eligibility_response + eligibility_cache_store
   - HAL tools fetch_eligibility_271 / fetch_availity_eligibility
   - AVAILITY_USE_DEMO + AVAILITY_LIVE_FALLBACK_DEMO (live scope may be unauthorized;
     demo Coverages-Complete-i works today; Standard Plan required for real patients)
   - SoftDent extract often lacks memberId/payerId/NPI on patient row — plan how to
     resolve those fields honestly (gaps ≠ invent).
6. Prefer compose/extend existing modules over new vendors. Rank MUST / SHOULD / NICE.
   Coding plan with concrete files. End with APPROVAL CHECKLIST.

OUTPUT FORMAT (strict markdown):
# Verdict — Availity eligibility in HAL patient dossier
## 0. Operator Intent (quote; consult-only)
## 1. Current State Audit (dossier vs clearinghouse/Availity vs HAL tools)
## 2. Gap Map
Table: Area | Status | Gap | Effort | Depends on
## 3. Target Design
### 3A Data contract (dossier.eligibility section; empty≠$0; demo flag)
### 3B Fetch path (SoftDent patient → member/payer/NPI → Availity 271 → cache → dossier)
### 3C HAL UX (tool + summarize + OM widget; spoken excerpt PHI-safe)
### 3D Live vs demo honesty (Standard Plan gate; fallback messaging)
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
    ("NewRidgeFinancial2/docs/MOONSHOT_HAL_PATIENT_FULL_SUMMARY_APPLIED_2026-07-11.md", 60),
    ("NewRidgeFinancial2/docs/MOONSHOT_VOICE_NICE_AVAILITY_LIVE_APPLIED_2026-07-11.md", 50),
    ("NewRidgeFinancial2/patient_dossier_prompts.py", 80),
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
        "### EXTRACT: patient_dossier.py — build_patient_dossier header\n```python\n"
        + _extract_lines(nr2 / "patient_dossier.py", "def build_patient_dossier", "def format_dossier_markdown", 80)
        + "\n```"
    )
    parts.append(
        "### EXTRACT: clearinghouse_eligibility_adapter — fetch + status\n```python\n"
        + _extract_lines(
            nr2 / "clearinghouse_eligibility_adapter.py",
            "def fetch_eligibility_271",
            None,
            70,
        )
        + "\n```"
    )
    parts.append(
        "### EXTRACT: clearinghouse_live_clients — fetch_availity_271\n```python\n"
        + _extract_lines(
            nr2 / "clearinghouse_live_clients.py",
            "def _availity_acquire_token",
            None,
            50,
        )
        + "\n```"
    )
    parts.append(
        "### EXTRACT: clearinghouse_live_clients — fetch_availity_271 body\n```python\n"
        + _extract_lines(
            nr2 / "clearinghouse_live_clients.py",
            "def fetch_availity_271",
            None,
            90,
        )
        + "\n```"
    )
    parts.append(
        "### EXTRACT: apex_backend — patient-dossier API\n```python\n"
        + _extract_lines(
            nr2 / "apex_backend.py",
            '@app.get("/api/apex/patient-dossier/<patient_id>")',
            None,
            60,
        )
        + "\n```"
    )
    parts.append(
        "### EXTRACT: hal-agent.js — summarize_patient_dossier\n```javascript\n"
        + _extract_lines(
            nr2 / "site" / "hal-agent.js",
            "summarize_patient_dossier: {",
            None,
            50,
        )
        + "\n```"
    )
    parts.append(
        "### EXTRACT: hal-agent.js — fetch_eligibility_271 / fetch_availity_eligibility\n```javascript\n"
        + _extract_lines(
            nr2 / "site" / "hal-agent.js",
            "fetch_eligibility_271: {",
            None,
            80,
        )
        + "\n```"
    )
    parts.append(
        "### EXTRACT: clearinghouse_271_mapper — map_availity\n```python\n"
        + _extract_lines(
            nr2 / "clearinghouse_271_mapper.py",
            "def map_availity_eligibility_response",
            None,
            60,
        )
        + "\n```"
    )

    parts.append(
        """### LIVE FACTS
- SoftDent READ-ONLY forever. Never invent dollars. empty ≠ $0.
- PHI local-only; audit hashes patient ids (hal_patient_audit).
- Patient dossier (hal-10495): SoftDent extract demographics/appts/procs/claims/
  estimates — NO eligibility/Availity section yet.
- Availity Coverages wired (hal-10496): fetch_availity_271 + demo/live fallback;
  HAL tools fetch_eligibility_271 / fetch_availity_eligibility exist separately.
- Demo keys: scope healthcare-hipaa-transactions-demo works.
  Live scope unauthorized until Standard Plan; AVAILITY_LIVE_FALLBACK_DEMO=1.
- SoftDent extract schema gaps: often no memberId / DOB / payerId on sd_patients —
  do not invent; surface gaps honestly.
- Goal: compose dossier + Availity so OM/HAL can capture insurance benefits for a
  patient from SoftDent context (demo OK until live plan).
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
        "CONSULT ONLY — recommend how to put Availity eligibility into the HAL "
        "patient dossier. Do not apply. SoftDent READ-ONLY; empty ≠ $0; PHI local; "
        "demo until Standard Plan.\n\n"
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
        headers["X-Title"] = "NR2 Availity Dossier Eligibility Consult"

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
        f"# Moonshot AI — Availity Eligibility in HAL Patient Dossier (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Script:** `scripts/run_moonshot_availity_dossier_eligibility_consult.py`  \n"
        f"**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_AVAILITY_DOSSIER_ELIGIBILITY_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_AVAILITY_DOSSIER_ELIGIBILITY_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
