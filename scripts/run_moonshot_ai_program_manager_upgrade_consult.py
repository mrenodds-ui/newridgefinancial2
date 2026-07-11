"""Moonshot AI — Full program upgrade audit (8B/30B orchestrator + SoftDent/QB automation).

CONSULT ONLY. Operator request VERBATIM. Await approval before applying code.
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
You are an expert senior full-stack engineer, data architect, and AI systems integrator specializing in dental practice management software. 
I need you to audit, refactor, and massively upgrade my self-built dental practice financial dashboard. This dashboard is running in Chrome and integrates with SoftDent (via exports) and QuickBooks. It uses local/API-connected 8B and 30B LLMs. 
Currently, the SoftDent and QuickBooks integration is only partially functional via manual exports. I want this system to become fully functional, highly polished, beautifully organized, and driven by my AI models acting as the core "program manager."
Please evaluate my existing codebase and provide the complete, production-ready code to achieve the following:
### 1. AI Models as Program Manager (8B & 30B Integration)
* Establish a clear hierarchy: Use the 8B model for fast, real-time widget data parsing, text summaries, and UI UI-routing triggers. Use the 30B model for deep financial forecasting, cross-referencing SoftDent ledger data with QuickBooks, and generating monthly practice health audits.
* Build an "AI Orchestrator" middleware layer that routes user queries or data updates to the correct model.
* Implement structured JSON outputs from the LLMs so the dashboard widgets can read and render the AI's insights dynamically without breaking the UI.
### 2. Full SoftDent & QuickBooks Data Automation
* Build robust, fault-tolerant parsers for SoftDent and QuickBooks CSV/Excel exports.
* Map SoftDent data (production, collection, case acceptance, patient aging, scheduling metrics) and QuickBooks data (expenses, payroll, net profit, accounts payable) into a unified local database/state management system (e.g.,
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — senior NR2 Apex + HAL architect for
NewRidge Family Financial (Kansas dental S-corp; SoftDent + QuickBooks imports;
local HTTPS starship-bridge; Ollama GPU lanes chat8b + escalate30b).

CRITICAL CONSTRAINTS:
1. Answer the OPERATOR REQUEST VERBATIM again (RE-AUDIT #4). The operator message was CUT OFF
   mid-sentence at "unified local database/state management system (e.g.," — note truncation,
   assume SQLite/NR2 app_data as unified store. Deliver a complete consult for sections 1–2
   against the LIVE codebase NOW (build hal-10486), not earlier states.
2. ALREADY SHIPPED — do NOT rebuild:
   - MUST I0–I4, SHOULD S0–S3, NICE N0, T0–T5 (through hal-10481)
   - U0 (hal-10482): deep audit & forecast pack (30B monthly audit → SSE; NR2_DEEP_AUDIT)
   - U1 (hal-10483): ERA 835 X12/CSV payer/proc aggregates (no PHI; NR2_ERA835)
   - U2 (hal-10484): SoftDent×QB MoM reconciliation 5%/$500 (NR2_RECONCILIATION)
   - U2b (hal-10485): import quarantine + admin alerts (NR2_IMPORT_QUARANTINE)
   - U3 (hal-10486): dashboard layout schema + mosaic order (starship-bridge; NR2_DASHBOARD_LAYOUT)
3. CONSULT ONLY — DO NOT APPLY code. Paste-ready sketches labeled CONSULT ONLY. Wait for approve.
4. Ground EVERY recommendation in LIVE FACTS + attached excerpts. Evolve NR2 packs; no rewrite;
   no SoftDent write-back; never invent dollars; PHI local; empty ≠ $0.
5. Map CURRENT (post U0–U3) vs TARGET. Rank ONLY remaining gaps MUST/SHOULD/NICE with S/M/L
   effort and next-wave phases (V0..Vn). If the original operator ask is substantially met,
   say so clearly and focus on burn-in ops, staging validation, and polish gaps only.
6. End with APPROVAL CHECKLIST for next work only.

OUTPUT FORMAT (strict markdown):
# Verdict — AI Program Manager re-audit #4 (post U0–U3 / hal-10486)
## 0. Operator Intent (quote; note truncation; consult-only re-run)
## 1. Current Architecture Audit (what exists at hal-10486)
### 1A Orchestrator + deep audit/forecast (U0)
### 1B SoftDent + ERA 835 aggregates (U1) + DEF-001
### 1C QuickBooks + reconciliation (U2)
### 1D Unified DB + import poll/quarantine (T3/U2b)
### 1E Insights SSE + dashboard layout (N0/U3)
## 2. Gap Map — REMAINING only
Table: Area | Status | Gap | Effort | Depends on
## 3. Target Architecture (next wave only)
## 4. Coding Plan — Phase V0..Vn (CONSULT ONLY sketches for remaining work)
## 5. MUST / SHOULD / NICE ranked table (remaining)
## 6. Risks, PHI, SoftDent honesty, Rollback
## 7. Approval Checklist (next wave only)
DO NOT APPLY until operator says approve / proceed.
"""


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} lines truncated]"


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 12),
    ("NewRidgeFinancial2/docs/MOONSHOT_AI_PM_PHASE_U3_APPLIED_2026-07-11.md", 50),
    ("NewRidgeFinancial2/docs/MOONSHOT_AI_PM_PHASE_U2B_APPLIED_2026-07-11.md", 40),
    ("NewRidgeFinancial2/docs/MOONSHOT_AI_PM_PHASE_U2_APPLIED_2026-07-11.md", 40),
    ("NewRidgeFinancial2/docs/MOONSHOT_AI_PM_PHASE_U1_APPLIED_2026-07-11.md", 40),
    ("NewRidgeFinancial2/docs/MOONSHOT_AI_PM_PHASE_U0_APPLIED_2026-07-11.md", 40),
    ("NewRidgeFinancial2/docs/MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT3_2026-07-11.md", 40),
    ("NewRidgeFinancial2/site/data/hal-models.json", 40),
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

    for rel, max_lines in (
        ("NewRidgeFinancial2/apex_orchestrator_pack.py", 40),
        ("NewRidgeFinancial2/apex_deep_audit_pack.py", 40),
        ("NewRidgeFinancial2/apex_era835_pack.py", 40),
        ("NewRidgeFinancial2/apex_reconciliation_pack.py", 40),
        ("NewRidgeFinancial2/apex_import_quarantine_pack.py", 40),
        ("NewRidgeFinancial2/apex_dashboard_layout_pack.py", 40),
        ("NewRidgeFinancial2/apex_unified_db_pack.py", 50),
    ):
        path = REPO / rel
        if path.is_file():
            parts.append(
                f"### FILE: {rel}\n```python\n"
                + _truncate(path.read_text(encoding="utf-8", errors="replace"), max_lines)
                + "\n```"
            )

    parts.append(
        """### LIVE FACTS (hal-10486 — RE-AUDIT #4 after U0–U3)
- Program Manager upgrade waves shipped: I0–I4, S0–S3, N0, T0–T5, U0–U3/U2b.
- Orchestrator default ON; deep audit/forecast; ERA 835 aggregates; MoM reconciliation;
  import quarantine; dashboard layout schema on starship-bridge.
- Honesty rules enforced: empty ≠ $0; gap codes; no SoftDent write-back; PHI stripped on ERA.
- Operator request (verbatim) re-submitted. CONSULT ONLY — remaining gaps only.
- If operator sections 1–2 are substantially met, declare that and rank only residual polish/ops.
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
        "OPERATOR REQUEST (VERBATIM — do not rewrite) — RE-RUN #4 after U0–U3 / hal-10486:\n\n"
        f"{OPERATOR_REQUEST_VERBATIM}\n\n"
        "NOTE: Same truncated operator message. I0–I4, S0–S3, N0, T0–T5, and U0–U3/U2b "
        "are shipped on hal-10486. Re-audit ONLY remaining gaps. "
        "CONSULT ONLY — do not apply. Wait for approval.\n\n"
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
        "max_tokens": 16000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 AI Program Manager Upgrade Consult"

    print("Calling Moonshot AI (consult only — will not apply)...")
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
        f"# Moonshot AI — AI Program Manager Upgrade RE-AUDIT #4 (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10486 (post U0–U3 / U2b)  \n"
        f"**Prior:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT3_2026-07-11.md`  \n"
        f"**Script:** `scripts/run_moonshot_ai_program_manager_upgrade_consult.py`  \n"
        f"**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT4_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT4_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
