"""Moonshot AI — What next (CONSULT ONLY); operator avoiding GitHub/PR for now."""

from __future__ import annotations

import json
import os
import sys
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

OPERATOR_REQUEST_VERBATIM = "next".strip()

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex (hal-10561 + local HAL qwen3:32b).

Operator said only: "next". CRITICAL CONSTRAINT: operator is AVOIDING GitHub for now
(no PR open/merge, no gh auth work). Do NOT recommend landing the PR as the primary
next package. Pick the best NEXT local engineering package that improves live Apex/HAL
without requiring GitHub.

Already shipped on fix/main-validate-ci (local/workstation):
- Expert SE Phases 1–3, compact pages, import gate harden, inbox sync coherence
- Zero-scroll widgets (hal-10561)
- HAL GPU pin → qwen3:32b (hal-local:32b)
- HAL deterministic import-gap replies naming quickbooks.payroll + quickbooks.ap
- Live: readiness fresh; only optional QB payroll+AP missing; critical completeness 100%

Open NICE from Expert SE: REC-008 batch narratives, REC-009 voice context carry.
Optional hygiene: gitignore site/index.pre-apex.html (local only, no PR required).

CONSULT ONLY. Pick ONE primary next package + max 3 runner-ups.
Be blunt. No invented dollars. Prefer concrete Apex/HAL value over process theater.

OUTPUT:
# Verdict (one sentence)
## 0. Intent
## 1. Already Done (do not redo)
## 2. Recommended NEXT (single package) — must NOT require GitHub
Goal, why now, effort, files, validation gate
## 3. Runner-up options (max 3)
## 4. Approval checklist
DO NOT APPLY CODE.
"""


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No API key", file=sys.stderr)
        return 1
    model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    if "moonshot" not in (base_url or "").lower():
        model = str(
            os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2"
        ).strip()
    print(f"Using {key_name} @ {base_url} model={model}")
    user = (
        f"OPERATOR REQUEST (VERBATIM): {OPERATOR_REQUEST_VERBATIM}\n\n"
        "What should we do NEXT on NR2 Apex locally? CONSULT ONLY.\n"
        "Operator constraint: AVOID GITHUB — do not recommend PR/merge/gh auth as NEXT.\n"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 6000,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Whats Next Avoid GitHub"
    import urllib.request

    req = urllib.request.Request(
        base_url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            content = extract_message_content(json.loads(resp.read().decode()))
        status = "ok"
    except Exception as exc:
        content = str(exc)
        status = "error"
    header = (
        f"# Moonshot AI — What's Next (Avoid GitHub) (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n**Model:** {model}  \n**Key:** {key_name}  \n"
        f"**Status:** {status}  \n**Build:** hal-10561 + hal-local:32b  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_avoid_github_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"**Constraint:** avoid GitHub / PR for now.\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out = OUT / f"MOONSHOT_WHATS_NEXT_AVOID_GITHUB_{DATE}.md"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AVOID_GITHUB_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    print(out)
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
