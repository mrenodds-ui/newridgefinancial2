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
local HTTPS starship-bridge; local Ollama on R9700).

CRITICAL CONSTRAINTS:
1. Answer the OPERATOR REQUEST VERBATIM again (RE-AUDIT #8). The operator message was CUT OFF
   mid-sentence at "unified local database/state management system (e.g.," — note truncation,
   assume SQLite/NR2 app_data as unified store. Deliver a complete consult for sections 1–2
   against the LIVE codebase NOW (tip after f3281f5 / hal-10493 + single-24B local AI), not earlier states.
2. ALREADY SHIPPED — do NOT rebuild:
   - Feature waves through W0–W2 (hal-10492): orchestrator, SoftDent/QB automation, unified DB,
     ERA, reconciliation, import DQ/cron, quarantine UI, extended metrics, burn-in telemetry packs
   - X0–X2 (hal-10493): burn-in ops runbooks; operator later ENABLED flags + Task Scheduler on this machine
   - REAUDIT7 declared PROGRAM COMPLETE PENDING BURN-IN; burn-in was then executed
   - Single-24B local AI (commit f3281f5): all approved local lanes → `hal-local:24b` (Q4_K_M) on
     R9700 only; OLLAMA_MAX_LOADED_MODELS=1; loopback-only; dual 8B+30B NOT auto-routed (files retained).
     Original request said 8B/30B hierarchy — architecture EVOLVED to one 24B; acknowledge this honestly.
3. CONSULT ONLY — DO NOT APPLY code. Wait for approve.
4. Ground EVERY recommendation in LIVE FACTS. Evolve NR2; no rewrite; no SoftDent write-back;
   never invent dollars; PHI local; empty ≠ $0.
5. If sections 1–2 are COMPLETE after burn-in + single-24B, say so CLEARLY as the primary verdict.
   Rank ONLY residual items. Prefer:
   - confirm "program complete" (or residual Future-vendor only)
   - optional tiny polish ONLY if grounded in real gaps
   - Future vendor items (QB Online API, SoftDent live API, ERA write-back; optional external 12GB GPU for separate 8B)
   Do NOT invent a large new feature wave (Y0..) unless a real MUST gap remains.
6. End with APPROVAL CHECKLIST (Future vendor / optional polish only).

OUTPUT FORMAT (strict markdown):
# Verdict — AI Program Manager re-audit #8 (post burn-in + single-24B)
## 0. Operator Intent (quote; note truncation; consult-only re-run)
## 1. Current Architecture Audit (what exists NOW) — brief
## 2. Gap Map — REMAINING only
Table: Area | Status | Gap | Effort | Depends on
## 3. Target Architecture (next wave only — or NONE if complete)
## 4. Coding Plan — only if MUST gaps remain (else state NO NEW CODE)
## 5. MUST / SHOULD / NICE ranked table (remaining)
## 6. Risks, PHI, SoftDent honesty, Rollback
## 7. Approval Checklist (Future / optional only)
DO NOT APPLY until operator says approve / proceed.
"""


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} lines truncated]"


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 12),
    ("NewRidgeFinancial2/docs/HAL_LOCAL_24B_SINGLE_GPU_2026-07-11.md", 80),
    ("NewRidgeFinancial2/docs/MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT7_2026-07-11.md", 60),
    ("NewRidgeFinancial2/docs/MOONSHOT_AI_PM_PHASE_X0_X2_APPLIED_2026-07-11.md", 40),
    ("NewRidgeFinancial2/site/data/hal-models.json", 80),
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
        """### LIVE FACTS (RE-AUDIT #8 — post burn-in + single-24B)
- Feature program through W2 shipped; X0–X2 burn-in runbooks shipped; operator ENABLED burn-in flags + Task Scheduler on this workstation.
- Local AI: single `hal-local:24b` (mistral-small3.1:24b Q4_K_M) on R9700 32GB; MAX_LOADED_MODELS=1; lanes chat8b/reason21b/escalate30b/coder32b → same 24B; cloudReasoning still off.
- Prompt suite + 30m stability PASSED; loopback OLLAMA_HOST=127.0.0.1; rollback script exists for dual 8B+30B.
- Honesty rules enforced. SoftDent read-only. Empty ≠ $0.
- Original operator ask wanted 8B+30B hierarchy; evolved to one 24B — judge whether sections 1–2 intent is still met.
- Prefer PROGRAM COMPLETE (Future vendor APIs only) if accurate.
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
        "OPERATOR REQUEST (VERBATIM — do not rewrite) — RE-RUN #8 after burn-in + single-24B:\n\n"
        f"{OPERATOR_REQUEST_VERBATIM}\n\n"
        "NOTE: Same early-afternoon upgrade message. Feature waves through W2 + X0–X2 + burn-in "
        "enablement + single-24B local AI are now live. Re-audit ONLY remaining gaps. "
        "Prefer 'program complete / Future vendor only' if accurate. CONSULT ONLY — do not apply.\n\n"
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
        f"# Moonshot AI — AI Program Manager Upgrade RE-AUDIT #8 (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** tip after f3281f5 (hal-10493 + single-24B)  \n"
        f"**Prior:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT7_2026-07-11.md`  \n"
        f"**Script:** `scripts/run_moonshot_ai_program_manager_upgrade_consult.py`  \n"
        f"**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT8_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT8_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
