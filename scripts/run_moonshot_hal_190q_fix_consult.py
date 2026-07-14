"""Moonshot AI — How to fix HAL 190Q issues (CONSULT ONLY → REPORT).

Operator: ask moonshot how to fix the 190 questions issues and report.
Does NOT apply code. Produces engineer-grade remediation report with REAL paths.
"""

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

OPERATOR_REQUEST_VERBATIM = (
    "ask moonshot how to fix the 190 questons issues and report"
).strip()

SCORECARD = {
    "successRate": 100.0,
    "avgMsAll": 52830.7,
    "qualityPassRate": 26.3,
    "deliverableRate": 27.9,
    "readOnlyOkRate": 25.0,
    "consentOkRate": 75.0,
    "yesNoLeadRate": 90.9,
    "directAnswerRate": 99.5,
    "cotLeakRate": 0.0,
    "laneCounts": {"chat8b": 98, "reason21b": 73, "escalate30b": 7, "local": 12},
    "avgMsByLane": {
        "chat8b": 57599.8,
        "reason21b": 54449.2,
        "escalate30b": 59751.6,
        "local": 0.2,
    },
}

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL (hal-10561 +
hal-local:32b / qwen3:32b Q4_K_M on R9700).

Operator asked how to FIX the issues found in the HAL 190-question eval, and wants
a REPORT. CONSULT ONLY — DO NOT claim you applied code.

Context — 190Q scorecard (already measured):
- Technical success 100%; CoT leak 0%; direct answer 99.5%; yes/no lead 90.9%
- FAIL: quality pass 26.3%; deliverable 27.9%; avg latency ~53s; read-only OK 25%
- Consent OK 75% (marginal)
- All model lanes map to hal-local:32b today (lane keys chat8b/reason21b/escalate30b
  are routing labels only — do not recommend loading 8B concurrently unless rollback)

Known failure modes from prior findings report:
1) Ignores brevity ("two sentences" / "one sentence") — verbose dumps
2) Deliverables missing when staff asked for steps/paths
3) Read-only scoring often fails even when local-policy correctly blocks writes —
   may be rubric ("read-only" literal) vs answer wording ("cannot post") mismatch
4) Latency ~50s+ on 32B for short asks
5) Unknown CARC codes risk speculative invention

REAL paths to prescribe against (do not invent fictional trees):
- NewRidgeFinancial2/nr2_hal_gateway.py — try_local_policy_reply, clean_gateway_text,
  evaluate_query, call_ollama_chat, options/keep_alive
- scripts/hal_eval_scoring.py — score_answer, has_read_only_mention, has_deliverable
- NewRidgeFinancial2/site/hal-core.js / hal-agent.js — browser voice/SSE if relevant
- NewRidgeFinancial2/apex_hal_cache_warm_pack.py — keep-alive already shipped
- Prefer additive Apex/HAL fixes; empty ≠ $0; no invented dollars; no SoftDent write-back

OUTPUT (strict markdown):
# Verdict (one sentence)
## 0. Operator Intent (verbatim)
## 1. Problem Diagnosis (ranked; blunt)
## 2. Fix Package (ordered phases) — each: goal, why, effort, REAL files, validation gate
## 3. What NOT to redo (already shipped / traps)
## 4. Acceptance Scorecard Targets (post-fix)
## 5. Executive Summary (5 bullets)
## 6. Approval checklist
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

    prior = DOCS / "MOONSHOT_HAL_190Q_REPORT_2026-07-12.md"
    prior_excerpt = ""
    if prior.is_file():
        prior_excerpt = prior.read_text(encoding="utf-8")[:6000]

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Produce a FIX REPORT for the HAL 190Q failures. CONSULT ONLY.\n\n"
        f"SCORECARD JSON:\n{json.dumps(SCORECARD, indent=2)}\n\n"
        f"PRIOR FINDINGS EXCERPT:\n{prior_excerpt}\n"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 10000,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 HAL 190Q Fix Consult"
    import urllib.request

    req = urllib.request.Request(
        base_url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            content = extract_message_content(json.loads(resp.read().decode()))
        status = "ok"
    except Exception as exc:
        content = str(exc)
        status = "error"
    header = (
        f"# Moonshot AI — HAL 190Q Fix Plan (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n**Model:** {model}  \n**Key:** {key_name}  \n"
        f"**Status:** {status}  \n**Build:** hal-10561 + hal-local:32b  \n"
        f"**Source eval:** `MOONSHOT_HAL_190Q_REPORT_2026-07-12.md` / "
        f"`HAL_190Q_EVAL_2026-07-12.json`  \n"
        f"**Script:** `scripts/run_moonshot_hal_190q_fix_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out = OUT / f"MOONSHOT_HAL_190Q_FIX_CONSULT_{DATE}.md"
    doc = DOCS / f"MOONSHOT_HAL_190Q_FIX_CONSULT_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    print(out)
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
