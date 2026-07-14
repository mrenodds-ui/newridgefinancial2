"""Moonshot AI — Validate detailed compact-pages plan (CONSULT ONLY).

Sends the drafted implementation plan for validation + opinion.
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
make a detailed plan and run it through moonshot ai for validation and his opinion and then report
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — principal engineer validating a DRAFT
implementation plan for NewRidge Financial 2.0 Apex page compaction.

Role: plan reviewer / architecture validator. Be blunt. Cite specific plan sections.
Do NOT write application code. Do NOT apply changes. Opinion + concrete plan edits only.

CRITICAL:
1. Answer the operator request: validate the detailed plan, give your opinion, report.
2. CONSULT ONLY — no code patches, no file edits in your reply beyond suggesting plan text.
3. Use the attached DETAILED PLAN as the artifact under review, plus prior consult context.
4. Explicitly state: APPROVE / CONDITIONAL APPROVE / REJECT.
5. If conditional, list required plan edits before coding may start.
6. Especially stress-test: Claims kanban + HAL chat vs “no scroll” contract; empty-collapse
   global pass side effects; motion kill vs “dead UI”; Phase 3 size audit scope.
7. Keep honesty rules: empty ≠ $0.

OUTPUT FORMAT (strict markdown):
# Verdict (APPROVE | CONDITIONAL APPROVE | REJECT) — 2–4 sentences
## 0. Operator Intent
## 1. Plan Strengths (what to keep)
## 2. Plan Weaknesses / Risks (ranked)
Table: ID | Severity | Issue | Why it matters | Required plan edit
## 3. Phase Order Opinion (keep / reorder / merge) with rationale
## 4. First-Viewport Contract Stress Test (Claims, HAL, Financial)
## 5. Recommended Plan Edits (copy-pasteable bullets)
## 6. What To Code First After Approval (still consult — do not code)
## 7. Final Opinion to Operator
DO NOT APPLY CODE.
"""


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} lines truncated]"


def build_context() -> str:
    parts: list[str] = []
    plan = DOCS / "MOONSHOT_COMPACT_PAGES_DETAILED_PLAN_2026-07-11.md"
    prior = DOCS / "MOONSHOT_COMPACT_PROFESSIONAL_PAGES_CONSULT_2026-07-11.md"
    if plan.is_file():
        parts.append(
            "### DETAILED PLAN UNDER REVIEW\n```md\n"
            + plan.read_text(encoding="utf-8", errors="replace")
            + "\n```"
        )
    else:
        parts.append("### DETAILED PLAN UNDER REVIEW\n(missing)")
    if prior.is_file():
        parts.append(
            "### PRIOR CONSULT (source)\n```md\n"
            + _truncate(prior.read_text(encoding="utf-8", errors="replace"), 160)
            + "\n```"
        )

    collapse = REPO / "NewRidgeFinancial2" / "apex_financial_console_pack.py"
    if collapse.is_file():
        text = collapse.read_text(encoding="utf-8", errors="replace")
        i = text.find("def collapse_empty_large")
        chunk = text[i : i + 900] if i >= 0 else "(collapse_empty_large not found)"
        parts.append(
            "### EXTRACT: collapse_empty_large (already shipped)\n```python\n"
            + _truncate(chunk, 40)
            + "\n```"
        )

    parts.append(
        """### LIVE FACTS
- Build: hal-10502 Apex Bridge at https://127.0.0.1:8765/
- Import readiness fresh after critical-only completeness fix; widgets load again.
- Operator complaint: all pages unorganized, huge wobbling widgets, want compact professional,
  little scroll.
- Prior Moonshot consult prescribed 5 phases (motion → empty collapse → size → subpages → polish).
- Engineer drafted DETAILED PLAN above for validation.
- Financial already uses strip console + selective collapse_empty_large; other pages lag.
- Many packs still emit size l/xl/full (subpages, sync status, softdent production, etc.).
- Consult-only until operator approves coding after this validation report.
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
        "Validate the attached DETAILED IMPLEMENTATION PLAN. Give blunt opinion, "
        "required edits, APPROVE / CONDITIONAL APPROVE / REJECT. CONSULT ONLY.\n\n"
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
        "max_tokens": 12000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Compact Pages Plan Validation"

    print("Calling Moonshot AI (plan validation — will not apply)...")
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
        f"# Moonshot AI — Compact Pages Detailed Plan Validation (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Plan reviewed:** `MOONSHOT_COMPACT_PAGES_DETAILED_PLAN_2026-07-11.md`  \n"
        f"**Script:** `scripts/run_moonshot_compact_pages_plan_validation_consult.py`  \n"
        f"**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_COMPACT_PAGES_PLAN_VALIDATION_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_COMPACT_PAGES_PLAN_VALIDATION_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
