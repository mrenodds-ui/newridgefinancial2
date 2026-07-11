"""Moonshot AI — Coding for missing widgets W-01..W-10 + HAL wiring (CONSULT ONLY).

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
ask moonoshot for coding of thiese widgets and how to wire them to hal, report and wait for approval
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — Apex instrumentation engineer + HAL board
control architect for NewRidge Financial 2.0 (NR2), local HTTPS starship-bridge app
(SoftDent + QuickBooks, local HAL).

CRITICAL CONSTRAINTS:
1. Answer the operator request VERBATIM: provide CODING for the missing widgets from
   MOONSHOT_MISSING_WIDGETS_LOOK_CONSULT (W-01..W-10) AND how to WIRE THEM TO HAL.
   Then REPORT and WAIT FOR APPROVAL — do not apply.
2. CONSULT ONLY — DO NOT APPLY / DO NOT CODE into the live repo. Paste-ready specs
   and foundation snippets are allowed in the report only, clearly labeled CONSULT ONLY.
3. Never invent dollar amounts, claim IDs, patients, ERA %, or clinical facts.
   Payloads use null/empty or PLACEHOLDER structure only.
4. Follow existing NR2 patterns:
   - Backend page packs (Python) emit widget specs into apex_backend mosaic.
   - Frontend apex-core.js Widget class switches on spec.type (or new type branches).
   - HAL wiring via resolve_hal_board_actions: regex → navigate + focus_widget /
     highlight_widget (+ optional set_inputs / refresh). Ask-HAL button on widgets
     already posts to board actions.
5. Cover ALL ten widgets W-01..W-10. For each: new type id, widgetId, page, data
   builder sketch, JS render notes, CSS notes, HAL phrase → action map.
6. Prefer one new pack module (e.g. apex_missing_widgets_pack.py) + focused
   apex-core.js type branches + resolve_hal_board_actions focus_rules additions.
7. Phased plan matching prior consult: Phase 1 quick wins (W-06, W-03, W-05, W-08,
   W-10) then Phase 2 (W-04, W-09, W-01, W-02, W-07). Honest empty when imports missing.
8. PHI: anonymize patient display (initials / hashed id) for W-06, W-08, W-09.
9. End with explicit APPROVAL CHECKLIST — STOP until operator says approve/proceed.

OUTPUT FORMAT (strict markdown):
# Verdict
## 0. Operator Intent (quote; confirm consult-only / wait for approval)
## 1. Architecture (files to touch; pack vs core vs HAL)
## 2. Coding Spec Per Widget (W-01..W-10)
For each: type, widgetId, page, payload JSON shape, Python builder sketch,
JS/CSS render sketch, honesty/empty, effort
## 3. HAL Wiring Map
Table: phrase patterns | navigate page | focus widgetId | notes
Plus paste-ready focus_rules tuples (CONSULT ONLY)
## 4. Ask-HAL / Board Action Integration
How ask-hal on each widget + any new board action types (prefer reuse existing)
## 5. Implementation Phases + Validation Gates (DO NOT APPLY)
## 6. Approval Checklist
DO NOT APPLY until operator says approve / proceed (phase or all).
"""


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 20),
    ("NewRidgeFinancial2/docs/MOONSHOT_MISSING_WIDGETS_LOOK_CONSULT_2026-07-11.md", 200),
    ("NewRidgeFinancial2/apex_bar_trend_page_org_pack.py", 80),
    ("NewRidgeFinancial2/apex_backend.py", 120),
    ("NewRidgeFinancial2/site/apex-core.js", 100),
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

    # Focused extract of HAL board resolver focus_rules
    apex = REPO / "NewRidgeFinancial2" / "apex_backend.py"
    if apex.is_file():
        text = apex.read_text(encoding="utf-8", errors="replace")
        start = text.find("def resolve_hal_board_actions")
        end = text.find("\ndef ", start + 10) if start >= 0 else -1
        if start >= 0:
            chunk = text[start : (end if end > start else start + 8000)]
            parts.append(
                "### EXTRACT: resolve_hal_board_actions (HAL wiring pattern)\n"
                f"```python\n{_truncate(chunk, 180)}\n```"
            )

    parts.append(
        """### LIVE FACTS
- Build ~hal-10441+. Apex mosaic + HAL board control already live.
- Missing widgets from prior consult (LOOK): W-01 Expense Treemap, W-02 Procedure Scatter,
  W-03 Denial Pareto, W-04 Treatment Pipeline, W-05 Pre-Auth Lanes, W-06 Unapplied Float,
  W-07 Cash Bridge, W-08 Verification Matrix, W-09 Operatory Board, W-10 Recall Gauge.
- HAL board actions already: sync_imports, refresh_page, navigate, focus_widget,
  highlight_widget, set_inputs, narrative_*, claims kanban filters, etc.
- focus_rules tuples: (regex, widgetId, page|None) → navigate + focus + highlight.
- Widgets get Ask-HAL button via apex-core.js; board control is deterministic + safe.
- Hard rules: never invent $; honest empty; PHI anonymize; CONSULT ONLY until approve.
- Operator wants: CODING for these widgets + HAL wiring; REPORT; WAIT FOR APPROVAL.
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
        "Provide coding specs for missing widgets W-01..W-10 and how to wire them to HAL. "
        "CONSULT ONLY — report and wait for approval. Do not apply code.\n\n"
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
        headers["X-Title"] = "NR2 Missing Widgets Coding + HAL Wire"

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
        f"# Moonshot AI — Missing Widgets Coding + HAL Wiring (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** ~hal-10441+  \n"
        f"**Prior look consult:** `MOONSHOT_MISSING_WIDGETS_LOOK_CONSULT_2026-07-11.md`  \n"
        f"**Script:** `scripts/run_moonshot_missing_widgets_coding_hal_consult.py`  \n"
        f"**Apply:** DO NOT APPLY / WAIT FOR OPERATOR APPROVAL.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_MISSING_WIDGETS_CODING_HAL_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_MISSING_WIDGETS_CODING_HAL_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
