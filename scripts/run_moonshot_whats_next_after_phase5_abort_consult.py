"""Moonshot AI — What's next after Phase 4 + aborted Phase 5 eval (CONSULT ONLY).

Operator pattern: "next" → Moonshot consult; do not apply code.
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

OPERATOR_REQUEST_VERBATIM = "next"

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL
(hal-10561 + hal-local:32b / qwen3:32b Q4_K_M on R9700).

Operator said "next" — produce the SINGLE best next local work package.
CONSULT ONLY — DO NOT claim you applied code.
Prefer additive Apex/HAL/data fixes. Avoid GitHub/PR as the primary package.
Do not invent fictional file trees — only real paths listed below.

JUST SHIPPED (HAL 190Q Phase 4 — 39cf104):
- CARC_BRIEFS (25) + CAS_BRIEFS (10); whitelist before LLM; hard unknown refuse
- test_carc_whitelist.py; MOONSHOT_HAL_190Q_FIX_PHASE4_APPLIED

JUST SHIPPED (prior): WHY-ERRORS (2cbef60), Phase 1–3 (325d24a/f225b2b/faa3113)

PHASE 5 STATUS — STARTED THEN ABORTED (NOT COMPLETE):
- Script: scripts/run_moonshot_hal_190q_phase5_eval.py
- Consult said: live full 190Q re-run via evaluate_query; targets quality≥85%,
  read-only 100%, avg≤15s, CARC halluc 0%
- Actual run: warm OK; Q1–7 local-policy OK (~0ms, qualityPass=True);
  Q8–10 reason21b FAIL empty_response (~42–56s each); Q11 local OK; then
  process exited early (exit 1) — only 11/190 asked; NO final
  HAL_190Q_EVAL_POST_PHASE4 / PHASE5_REPORT artifacts
- Partial: .local_logs/.../HAL_190Q_POST_PHASE4_PARTIAL_2026-07-12.json
- Smoke earlier: local CARC 45 / XX-99 / QB-post all correct

STILL OPEN (pick ONE as NEXT if highest leverage):
- Finish/repair Phase 5: diagnose empty_response on Ollama reason21b lane,
  resume 190Q, deliver go/no-go report (measurement still incomplete)
- Collections/Daysheet export gap → empty revenue-composition
- Other additive SoftDent/QB/HAL ops only if clearly higher ROI

Do NOT redo Phases 1–4 or WHY-ERRORS. Do not invent SoftDent write-back / dollars.

REAL PATHS:
- scripts/run_moonshot_hal_190q_phase5_eval.py
- scripts/run_moonshot_hal_190q_eval.py, scripts/hal_eval_scoring.py
- NewRidgeFinancial2/nr2_hal_gateway.py (evaluate_query, extract/clean text)
- NewRidgeFinancial2/apex_hal_cache_warm_pack.py
- NewRidgeFinancial2/softdent_practice_exports.py, practice_source_access.py
- Prefer empty ≠ $0; no PHI invention

OUTPUT (strict markdown):
# Verdict (one sentence — THE next package)
## 0. Operator Intent (verbatim: next)
## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
## 2. Runner-ups (2–3, why not now)
## 3. What NOT to redo
## 4. Acceptance criteria
## 5. Executive Summary (5 bullets)
## 6. Approval checklist
DO NOT APPLY CODE. Prefer one clear next over a laundry list.
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

    partial = OUT / "HAL_190Q_POST_PHASE4_PARTIAL_2026-07-12.json"
    partial_excerpt = ""
    if partial.is_file():
        rows = json.loads(partial.read_text(encoding="utf-8"))
        fails = [r for r in rows if not r.get("ok")]
        partial_excerpt = json.dumps(
            {
                "asked": len(rows),
                "ok": sum(1 for r in rows if r.get("ok")),
                "failed": fails,
                "sampleOk": [
                    {"q": r.get("query"), "lane": r.get("lane"), "ms": r.get("ms")}
                    for r in rows
                    if r.get("ok")
                ][:5],
            },
            indent=2,
        )[:4000]

    excerpts = []
    for name in (
        "MOONSHOT_WHATS_NEXT_AFTER_PHASE4_2026-07-12.md",
        "MOONSHOT_HAL_190Q_FIX_PHASE4_APPLIED_2026-07-12.md",
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:2500]}")

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Phase 4 APPLIED; Phase 5 ABORTED mid-run. Pick THE next package. CONSULT ONLY.\n\n"
        f"## PHASE 5 PARTIAL JSON SUMMARY\n{partial_excerpt}\n\n"
        + "\n\n".join(excerpts)
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 7000,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Whats Next After Phase5 Abort"
    import urllib.request

    print("Calling Moonshot AI (consult only — will not apply)...")
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
        f"# Moonshot AI — What's Next After Phase 5 Abort (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** hal-10561 + hal-local:32b  \n"
        f"**Prior:** Phase 4 (`39cf104`); Phase 5 aborted at ~11/190 (empty_response)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_phase5_abort_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_PHASE5_ABORT_{DATE}.md"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_PHASE5_ABORT_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    print(out)
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
