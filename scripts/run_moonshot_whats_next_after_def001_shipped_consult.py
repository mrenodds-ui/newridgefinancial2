"""Moonshot AI — What's next after DEF-001 shipped (CONSULT ONLY).

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
(hal-10564 + Phase 5 190Q GO + DEF-001 + hal-local:32b on R9700).

Operator said "next" — produce the SINGLE best next local work package.
CONSULT ONLY — DO NOT claim you applied code.
Prefer additive Apex/HAL/data fixes. Avoid GitHub/PR as the primary package.
Do not invent fictional file trees — only real paths listed below.

JUST SHIPPED (DEF-001 Collections honesty — c645460 / hal-10564):
- scan_collections_export_inbox; period-aware empty revenue-composition
- Financial gap strip; HAL policy:def-001-collections; refresh inbox scan
- Honesty: empty ≠ $0; no invented insurance/patient dollars
- Ops still may need SoftDent Collections export for live split

JUST SHIPPED (Phase 5 GO — 7e46a70 / 32214ac):
- Full 190Q: success 100%, quality ~98.4%, read-only 100%, avg ~14.1s, empty 0
- Verdict GO for staff production use on HAL safety/latency gates

JUST SHIPPED PRIOR:
- Cache coherence hal-10563; KPI density hal-10562
- WHY-ERRORS SQLite timeout; CARC Phase 4; HAL Phases 1–3
- REC-005/007/008/009; QB payroll/AP inbox

STILL OPEN (pick ONE as NEXT if highest leverage):
- Close NO_PERIOD_ROW / daysheet present but period null (period sync ingest)
- Ops-only SoftDent Collections CSV for 2026-07 (if code loop is complete)
- Browser smoke of density/cache/DEF-001 after hard-refresh
- Other additive SoftDent/QB/HAL only if clearly higher ROI

Do NOT redo DEF-001 honesty gates, Phase 1–5 190Q, KPI density, cache
coherence, WHY-ERRORS timeout, CARC Phase 4. empty ≠ $0; no SoftDent write-back.

REAL PATHS:
- NewRidgeFinancial2/softdent_dashboard_period_sync.py
- NewRidgeFinancial2/softdent_practice_exports.py
- NewRidgeFinancial2/apex_softdent_hardening_pack.py
- NewRidgeFinancial2/apex_financial_console_pack.py
- NewRidgeFinancial2/apex_backend.py
- NewRidgeFinancial2/nr2_hal_gateway.py
- NewRidgeFinancial2/site/apex-core.js, financial page widgets
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
        "MOONSHOT_COLLECTIONS_DAYSHEET_APPLIED_2026-07-12.md",
        "MOONSHOT_HAL_190Q_PHASE5_REPORT_2026-07-12.md",
        "MOONSHOT_WHATS_NEXT_AFTER_DEF001_2026-07-12.md",
        "MOONSHOT_CACHE_COHERENCE_APPLIED_2026-07-12.md",
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:2800]}")

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "DEF-001 + Phase 5 GO APPLIED. Pick THE next local package. CONSULT ONLY.\n\n"
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
        headers["X-Title"] = "NR2 Whats Next After DEF001"
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
        f"# Moonshot AI — What's Next After DEF-001 + Phase 5 GO (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** hal-10564 + Phase 5 GO  \n"
        f"**Prior:** DEF-001 (`c645460`); Phase 5 GO (`7e46a70` / `32214ac`)  \n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_def001_shipped_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out = OUT / f"MOONSHOT_WHATS_NEXT_AFTER_DEF001_SHIPPED_{DATE}.md"
    doc = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_DEF001_SHIPPED_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    print(out)
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
