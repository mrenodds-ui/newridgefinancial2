"""Moonshot AI — How to improve the NR2 program (CONSULT ONLY).

Operator request is passed VERBATIM. Do not rewrite operator intent.
Does NOT apply any code. Await operator approval before coding.
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
ask moonshot ai hiw to improve the program. report do not code intil approval
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — product architect + HAL systems engineer
for NewRidge Financial 2.0 (NR2), a local HTTPS Apex starship-bridge app for a Kansas
dental S-corp (SoftDent + QuickBooks imports, local HAL).

CRITICAL CONSTRAINTS:
1. Answer the operator request VERBATIM: how to improve the program — REPORT ONLY.
2. CONSULT ONLY — DO NOT APPLY / DO NOT CODE until operator explicitly approves.
3. Use LIVE FACTS + attached context as ground truth. Never invent dollars, claim IDs,
   patients, ERA %, or clinical facts.
4. Cover the WHOLE program: Apex pages, HAL control, SoftDent/QB imports, Claims workbench,
   Narratives, Taxes/CPA, Financial/EBITDA, A/R, Documents, Office Manager, reliability,
   UX polish, data honesty, operator workflow.
5. Rank improvements MUST / SHOULD / NICE with rationale and effort (S/M/L).
6. Prefer additive Apex instruments and HAL board-actions over resurrecting retired mockups.
7. Call out what is already strong (do not recommend redoing shipped work without reason).
8. Phased plan with validation gates. State clearly: Moonshot/Cursor codes only after approve.

OUTPUT FORMAT (strict markdown):
# Verdict
## 0. Operator Intent (quote; confirm consult-only; no code until approval)
## 1. Current Program Snapshot (what is strong vs weak at hal-10380)
## 2. Top Improvements — Ranked MUST / SHOULD / NICE
Table: ID | Rank | Area | Improvement | Why | Effort | Depends on
## 3. Page-by-Page Improvement Map
financial, taxes, softdent, quickbooks, ar, claims, narratives, documents, library,
office-manager, hal — 2–4 concrete boosts each (or “hold”).
## 4. HAL Direction Gaps
What HAL should know/control next (board-actions, chips, honesty).
## 5. Data / Import / Honesty Gaps
SoftDent, QB, ERA, attachments — what blocks better UI.
## 6. Recommended Phases (I0 validate → In) + Validation Gate
## 7. Risks, PHI / CPA disclaimer & Rollback
DO NOT APPLY until operator says proceed / approve.
"""


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 20),
    ("NewRidgeFinancial2/docs/MOONSHOT_CLAIMS_KANBAN_APPLIED_2026-07-10.md", 60),
    ("NewRidgeFinancial2/docs/MOONSHOT_CLAIMS_MOCKUP_PARITY_CONSULT_2026-07-10.md", 80),
    ("NewRidgeFinancial2/docs/MOONSHOT_CLAIMS_NARRATIVES_APPLIED_2026-07-10.md", 50),
    ("NewRidgeFinancial2/docs/MOONSHOT_SOFTDENT_FULL_EXTRACT_APPLIED_2026-07-10.md", 50),
    ("NewRidgeFinancial2/docs/MOONSHOT_IMPORT_HEALTH_CPA_TAX_APPLIED_2026-07-10.md", 40),
]


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} lines truncated]"


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

    # Light live inventory of Apex pages / widget builders
    backend = REPO / "NewRidgeFinancial2" / "apex_backend.py"
    if backend.is_file():
        text = backend.read_text(encoding="utf-8", errors="replace")
        for marker, label, max_lines in (
            ("APEX_PAGES", "APEX_PAGES", 30),
            ("def _claims_widgets", "_claims_widgets head", 40),
            ("def resolve_hal_board_actions", "resolve_hal_board_actions head", 40),
        ):
            idx = text.find(marker)
            if idx < 0:
                parts.append(f"### EXCERPT: {label}\n(missing)")
                continue
            parts.append(
                f"### EXCERPT: apex_backend.py::{label}\n```python\n{_truncate(text[idx : idx + 3500], max_lines)}\n```"
            )

    parts.append(
        """### LIVE FACTS (hal-10380 — consult time)
- Epoch: nr2-apex starship bridge (local HTTPS). SoftDent + QuickBooks import-backed.
- Recently shipped: claims 30/60/90 shelves + claim drawer + narratives insurance HAL;
  voice-to-narrative; payer appeal templates; SoftDent full extract; Claims Workbench
  read-only kanban (mockup parity Phase 1); HAL focus/filter for kanban; narratives
  center-box draft apply fix (pending operator verify).
- Claims kanban: NO drag write-back; ERA/attachment/risk only when on import.
- Narratives: interactive bridge with context lock + payer generate + center composer.
- HAL: board-actions for sync, focus widgets, claims aging/kanban filters, narrative voice.
- Hard rules: never invent $; PHI local; consult-only until operator approves coding.
- Operator: how to improve the program — REPORT; do not code until approval.
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
        "CONSULT ONLY — improvement report. Do not apply code.\n"
        "Do not code until operator approval.\n\n"
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
        "max_tokens": 16000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Program Improvement Consult"

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
        f"# Moonshot AI — How to Improve the Program (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10380  \n"
        f"**Script:** `scripts/run_moonshot_program_improve_consult.py`  \n"
        f"**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_PROGRAM_IMPROVE_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_PROGRAM_IMPROVE_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
