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
1. Answer the OPERATOR REQUEST VERBATIM again (RE-AUDIT #7). The operator message was CUT OFF
   mid-sentence at "unified local database/state management system (e.g.," — note truncation,
   assume SQLite/NR2 app_data as unified store. Deliver a complete consult for sections 1–2
   against the LIVE codebase NOW (build hal-10493), not earlier states.
2. ALREADY SHIPPED — do NOT rebuild:
   - Feature waves through W0–W2 (hal-10492): orchestrator, SoftDent/QB automation, unified DB,
     ERA, reconciliation, import DQ/cron, quarantine UI, extended metrics, burn-in telemetry packs
   - REAUDIT6 X0–X2 (hal-10493): OPT-IN ops runbooks only
     (nr2_burnin_enable_flags.ps1, nr2_register_scheduled_tasks.ps1, validate_nr2_burnin.py).
     Burn-in flags remain DEFAULT OFF until operator executes scripts.
3. CONSULT ONLY — DO NOT APPLY code. Wait for approve.
4. Ground EVERY recommendation in LIVE FACTS. Evolve NR2; no rewrite; no SoftDent write-back;
   never invent dollars; PHI local; empty ≠ $0.
5. If sections 1–2 are COMPLETE pending operator burn-in enablement, say so CLEARLY as the
   primary verdict. Rank ONLY residual items. Prefer:
   - confirm "program complete / awaiting burn-in"
   - optional tiny polish ONLY if grounded in real gaps
   - Future vendor items (QB Online API, SoftDent live API, ERA write-back)
   Do NOT invent a large new feature wave (Y0..) unless a real MUST gap remains.
6. End with APPROVAL CHECKLIST (burn-in enablement and/or Future only).

OUTPUT FORMAT (strict markdown):
# Verdict — AI Program Manager re-audit #7 (post X0–X2 / hal-10493)
## 0. Operator Intent (quote; note truncation; consult-only re-run)
## 1. Current Architecture Audit (what exists at hal-10493) — brief
## 2. Gap Map — REMAINING only
Table: Area | Status | Gap | Effort | Depends on
## 3. Target Architecture (next wave only — or NONE if complete)
## 4. Coding Plan — only if MUST gaps remain (else state NO NEW CODE)
## 5. MUST / SHOULD / NICE ranked table (remaining)
## 6. Risks, PHI, SoftDent honesty, Rollback
## 7. Approval Checklist (burn-in enablement / Future only)
DO NOT APPLY until operator says approve / proceed.
"""


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} lines truncated]"


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 12),
    ("NewRidgeFinancial2/docs/MOONSHOT_AI_PM_PHASE_X0_X2_APPLIED_2026-07-11.md", 80),
    ("NewRidgeFinancial2/docs/MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT6_2026-07-11.md", 60),
    ("NewRidgeFinancial2/docs/MOONSHOT_AI_PM_PHASE_W2_APPLIED_2026-07-11.md", 30),
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
        ("scripts/nr2_burnin_enable_flags.ps1", 40),
        ("scripts/nr2_register_scheduled_tasks.ps1", 40),
        ("scripts/validate_nr2_burnin.py", 40),
    ):
        path = REPO / rel
        if path.is_file():
            lang = "powershell" if rel.endswith(".ps1") else "python"
            parts.append(
                f"### FILE: {rel}\n```{lang}\n"
                + _truncate(path.read_text(encoding="utf-8", errors="replace"), max_lines)
                + "\n```"
            )

    parts.append(
        """### LIVE FACTS (hal-10493 — RE-AUDIT #7 after X0–X2)
- Feature program through W2 is shipped. X0–X2 are opt-in ops scripts only.
- Burn-in flags still DEFAULT OFF until operator runs nr2_burnin_enable_flags.ps1.
- Task Scheduler not registered until operator runs nr2_register_scheduled_tasks.ps1.
- Honesty rules enforced throughout. SoftDent read-only.
- If original sections 1–2 are met, declare PROGRAM COMPLETE PENDING BURN-IN.
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
        "OPERATOR REQUEST (VERBATIM — do not rewrite) — RE-RUN #7 after X0–X2 / hal-10493:\n\n"
        f"{OPERATOR_REQUEST_VERBATIM}\n\n"
        "NOTE: Feature waves through W2 + X0–X2 burn-in runbooks are shipped on hal-10493. "
        "Re-audit ONLY remaining gaps. Prefer 'complete pending burn-in' if accurate. "
        "CONSULT ONLY — do not apply.\n\n"
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
        "max_tokens": 12000,
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
        f"# Moonshot AI — AI Program Manager Upgrade RE-AUDIT #7 (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10493 (post X0–X2)  \n"
        f"**Prior:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT6_2026-07-11.md`  \n"
        f"**Script:** `scripts/run_moonshot_ai_program_manager_upgrade_consult.py`  \n"
        f"**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT7_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT7_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
