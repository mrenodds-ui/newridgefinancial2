"""Moonshot AI — What's next after WHY-ERRORS + HAL 190Q Phase 1–3 (CONSULT ONLY).

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

Operator said "next" — produce the SINGLE best next local work package after
the items below were APPLIED. CONSULT ONLY — DO NOT claim you applied code.
Prefer additive Apex/HAL/data fixes. Avoid GitHub/PR as the primary package.
Do not invent fictional file trees — only real paths listed below.

JUST SHIPPED (WHY-ERRORS Phase 1+2 — 2cbef60):
- softdent_practice_exports.py: sqlite3.connect timeout=10.0 + PRAGMA busy_timeout=5000
  at three connect sites (read practice exports / sync / CSV ingest)
- practice_source_access.py: distinguish sqlite3.OperationalError; metric
  direct_import_lock_rejection_count (WARNING, no full traceback for locks)
- MOONSHOT_WHY_ERRORS_CONSULT/APPLIED_2026-07-12.md + test_why_errors_sqlite_lock.py

JUST SHIPPED (HAL 190Q Phase 1 — 325d24a):
- Post-gen constraints; write/CARC/empty≠$0 preflight; rubric recalibration

JUST SHIPPED (HAL 190Q Phase 2 — f225b2b):
- Structured deliverables (JSON steps/caution/references → numbered markdown + UI)

JUST SHIPPED (HAL 190Q Phase 3 — faa3113):
- Early SSE typing/ttft meta; onToken accumulate; Apex askHal streams;
  skip fake typewriter after live stream; test_hal_stream_ttft.py

STILL OPEN (pick ONE as NEXT if highest leverage):
- Live 190Q subset/full re-run to measure Phase 1–3 lift (eval only — no code)
- Phase 4: CARC whitelist hardening (unknown refuse done; known-code briefs sparse)
- Collections/Daysheet export gap → empty revenue-composition (data honesty)
- Other additive SoftDent/QB/HAL ops only if clearly higher ROI than above

Do NOT redo WHY-ERRORS lock fix or HAL Phases 1–3.

ALSO RECENTLY SHIPPED (context, do not redo):
- REC-005 ERA 835 depth, REC-007 HAL keep-alive/warm, REC-008 batch narratives,
  REC-009 voice context carry, QB payroll/AP atomic CSV → document-inbox

REAL PATHS:
- NewRidgeFinancial2/nr2_hal_gateway.py
- NewRidgeFinancial2/site/hal-core.js, hal-agent.js, apex-core.js, apex-narratives.js
- NewRidgeFinancial2/softdent_practice_exports.py, practice_source_access.py
- NewRidgeFinancial2/era835_parser.py, apex_era835_pack.py, apex_hal_cache_warm_pack.py
- NewRidgeFinancial2/apex_qb_export_inbox_pack.py
- scripts/hal_eval_scoring.py, scripts/run_moonshot_hal_190q_eval.py
- Prefer no SoftDent write-back; empty ≠ $0; no invented dollars/PHI

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

    excerpts = []
    for name in (
        "MOONSHOT_WHY_ERRORS_APPLIED_2026-07-12.md",
        "MOONSHOT_HAL_190Q_FIX_PHASE3_APPLIED_2026-07-12.md",
        "MOONSHOT_HAL_190Q_FIX_PHASE2_APPLIED_2026-07-12.md",
        "MOONSHOT_HAL_190Q_FIX_PHASE1_APPLIED_2026-07-12.md",
        "MOONSHOT_HAL_190Q_FIX_CONSULT_2026-07-12.md",
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:3200]}")

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "WHY-ERRORS + HAL Phase 1–3 APPLIED. Pick THE next local package. CONSULT ONLY.\n\n"
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
        headers["X-Title"] = "NR2 Whats Next After Why Errors"
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
        f"# Moonshot AI — What's Next After WHY-ERRORS + HAL 190Q Phase 1–3 (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** hal-10561 + hal-local:32b  \n"
        f"**Prior applied:** WHY-ERRORS (`2cbef60`) + Phase 1 (`325d24a`) + "
        f"Phase 2 (`f225b2b`) + Phase 3 (`faa3113`)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_why_errors_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_WHY_ERRORS_{DATE}.md"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_WHY_ERRORS_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    print(out)
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
