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
1. Answer the OPERATOR REQUEST VERBATIM: audit + upgrade plan for AI-as-program-manager
   (8B/30B) and full SoftDent/QB automation. The operator message was CUT OFF mid-sentence
   at "unified local database/state management system (e.g.," — note the truncation,
   assume SQLite/LocalStore/NR2 app_data as the intended unified store, and still deliver
   a complete consult for sections 1–2.
2. CONSULT ONLY — DO NOT APPLY code. Provide paste-ready sketches labeled CONSULT ONLY.
   Wait for operator approve/proceed.
3. Ground EVERY recommendation in LIVE FACTS + attached codebase excerpts. Prefer evolving
   existing NR2 (apex_backend, nr2_hal_gateway, hal-core lanes, import_sync, LocalStore,
   nr2_local_db) over a greenfield rewrite. Do not resurrect retired mockups.
4. Honesty: never invent dollars; SoftDent/QB are import/ODBC-backed; HAL never SoftDent
   write-back; PHI stays local; empty widgets stay empty.
5. Map CURRENT vs TARGET for: model lanes (chat8b / reason21b / escalate30b), board-actions
   vs LLM, import Direct-First vs CSV, unified state.
6. Rank MUST / SHOULD / NICE with effort S/M/L and phased plan + validation gates.
7. For coding sketches: additive packs (apex_*_pack.py), orchestrator module, JSON schemas
   for widget-safe AI insights, parser hardening — not a second dashboard.
8. End with APPROVAL CHECKLIST.

OUTPUT FORMAT (strict markdown):
# Verdict — Path to AI Program Manager + full SoftDent/QB automation
## 0. Operator Intent (quote; note truncation; consult-only)
## 1. Current Architecture Audit (what exists at hal-10470)
### 1A Model lanes & routing (8B/30B)
### 1B SoftDent import automation
### 1C QuickBooks import automation
### 1D Unified local state (LocalStore / SQLite / bundles)
### 1E Apex widget honesty / structured payloads
## 2. Gap Map (CURRENT → TARGET)
Table: Area | Status | Gap | Effort | Depends on
## 3. Target Architecture (AI Orchestrator + data plane)
Mermaid or clear layers: UI → board-actions → Orchestrator → 8B/30B → structured JSON → widgets
## 4. Coding Plan — Phase I0..In (CONSULT ONLY sketches)
### 4A AI Orchestrator middleware
### 4B Structured JSON insight schema for widgets
### 4C SoftDent parser / Direct-First hardening
### 4D QuickBooks mapping (expenses, payroll, net profit, AP)
### 4E Unified local DB / state
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
        return f"(marker not found: {start_marker[:60]})"
    if end_marker:
        end = text.find(end_marker, start + len(start_marker))
        chunk = text[start : (end if end > start else start + 14000)]
    else:
        chunk = text[start : start + 14000]
    return _truncate(chunk, max_lines)


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 12),
    ("NewRidgeFinancial2/README.md", 120),
    ("NewRidgeFinancial2/site/data/hal-models.json", 80),
    ("NewRidgeFinancial2/docs/MOONSHOT_PROGRAM_IMPROVE_APPLIED_2026-07-10.md", 40),
    ("NewRidgeFinancial2/docs/MOONSHOT_HAL_SAID_IMPROVE_FIX_APPLIED_2026-07-11.md", 50),
    ("NewRidgeFinancial2/docs/MOONSHOT_WHATS_WRONG_CONSULT_2026-07-10.md", 60),
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

    hal_core = REPO / "NewRidgeFinancial2" / "site" / "hal-core.js"
    parts.append(
        "### EXTRACT: hal-core.js — laneRuntime / escalate\n```js\n"
        + _extract_lines(hal_core, "function laneRuntime", "function laneReady", 40)
        + "\n```"
    )
    parts.append(
        "### EXTRACT: hal-core.js — preRoute escalate / chat8b\n```js\n"
        + _extract_lines(hal_core, "return { intent: \"escalation\", lane: \"escalate30b\"", None, 50)
        + "\n```"
    )

    gateway = REPO / "NewRidgeFinancial2" / "nr2_hal_gateway.py"
    if gateway.is_file():
        parts.append(
            "### EXTRACT: nr2_hal_gateway.py head\n```python\n"
            + _truncate(gateway.read_text(encoding="utf-8", errors="replace"), 80)
            + "\n```"
        )

    backend = REPO / "NewRidgeFinancial2" / "apex_backend.py"
    parts.append(
        "### EXTRACT: apex_backend.py — resolve_hal_board_actions head\n```python\n"
        + _extract_lines(backend, "def resolve_hal_board_actions", "def build_apex_ticker", 60)
        + "\n```"
    )

    import_sync = REPO / "NewRidgeFinancial2" / "import_sync.py"
    if import_sync.is_file():
        parts.append(
            "### EXTRACT: import_sync.py head + sync entry\n```python\n"
            + _truncate(import_sync.read_text(encoding="utf-8", errors="replace"), 70)
            + "\n```"
        )

    http = REPO / "NewRidgeFinancial2" / "nr2_http_server.py"
    parts.append(
        "### EXTRACT: nr2_http_server.py — evaluate-query\n```python\n"
        + _extract_lines(http, '@app.post("/api/hal/evaluate-query")', '@app.post("/api/hal/', 50)
        + "\n```"
    )

    local_db = REPO / "NewRidgeFinancial2" / "nr2_local_db.py"
    parts.append(
        "### EXTRACT: nr2_local_db.py schema head\n```python\n"
        + _truncate(local_db.read_text(encoding="utf-8", errors="replace"), 80)
        + "\n```"
    )

    parts.append(
        """### LIVE FACTS (hal-10470 — consult time)
- Epoch: NR2 Apex starship bridge (local HTTPS Chrome). SoftDent + QuickBooks import-backed.
- LLM lanes (Ollama GPU on workstation): chat8b (hal-chat:8b) fast; escalate30b (hal-escalate:30b)
  deep; optional reason21b / coder lanes in hal-models.json / hal-core.js.
- Routing today: deterministic board-actions FIRST (apex_backend.resolve_hal_board_actions),
  then /api/hal/evaluate-query → gateway/LLM. Not a full "AI Orchestrator" middleware yet.
- SoftDent: Direct-First / ODBC / Sensei DataSync preferred; CSV/Excel exports still used;
  import_sync + import_loader + softdent_* modules; honesty = empty KPIs when missing.
- QuickBooks: import-backed P&L/expenses style data; read-only; payroll/AP may be partial/absent.
- State: LocalStore keys + nr2_local_db SQLite (tasks, huddle, notes) + import bundles —
  not one fully unified warehouse yet.
- Recently shipped: program improve IMP-001..010; HAL-said pack (denials→Steve, sign-off,
  EOB backlog, payer sync, structured Remember) at hal-10470.
- Hard rules: never invent $; no SoftDent write-back from Apex; PHI local; consult-only until approve.
- Operator request truncated after "unified local database/state management system (e.g.,".
- Operator wants: Moonshot audit + production-ready coding plan/report (not apply yet).
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
        "NOTE: Operator message was truncated mid-sentence at unified DB. "
        "Complete the audit + upgrade consult for AI Program Manager (8B/30B) and "
        "full SoftDent/QB automation. CONSULT ONLY — do not apply. Wait for approval.\n\n"
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
        f"# Moonshot AI — AI Program Manager + SoftDent/QB Automation Upgrade (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10470  \n"
        f"**Script:** `scripts/run_moonshot_ai_program_manager_upgrade_consult.py`  \n"
        f"**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
