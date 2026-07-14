"""Moonshot AI — Cache problem diagnosis & fix report (CONSULT ONLY).

Operator request is passed VERBATIM. Do not rewrite operator intent.
Does NOT apply any code. Await operator approval before coding.
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

OPERATOR_REQUEST_VERBATIM = "ask moonshot ai about the cachi problem and report"

SYSTEM = """You are Moonshot AI — principal systems engineer for NR2 Apex HAL
(hal-10562 + hal-local:32b / qwen3:32b Q4_K_M on R9700).

Operator request (VERBATIM, typo preserved): "ask moonshot ai about the
cachi problem and report" — treat "cachi" as CACHE problem. Produce a
diagnosis + fix REPORT. CONSULT ONLY — DO NOT claim you applied code.

JUST SHIPPED (hal-10562 KPI density):
- ≤4 KPI tiles above fold; empty omit; Taxes → #taxes/planning
- SoftDent/QB/AR/OM vital strips; Financial ops strip
- Docs: MOONSHOT_KPI_DENSITY_FIX_APPLIED_2026-07-12.md

CACHE LAYERS IN PLAY (real; diagnose which is broken / confusing):

1) WIDGET STUB FAST-PATH (Expert SE Phase 3 / REC-007 adjacent)
   - File: NewRidgeFinancial2/apex_backend.py build_apex_widgets
   - Env: NR2_WIDGETS_STUB_FASTPATH default ON
   - On cold/expired miss (_fill=False): IMMEDIATELY returns warming=True
     stub with single widget id=warming-bridge, sourceNote=stub-fastpath,
     message "Warming import cache — KPIs appear when ready"
   - Spawns daemon thread to build_apex_widgets(..., _fill=True) into
     _WIDGETS_CACHE (TTL 15s)
   - Frontend apex-core.js: if payload.warming, setTimeout 750ms silent
     reload; IndexedDB paints stale-while-revalidate BEFORE network
   - RISK: stuck warming if fill fails silently; IDB shows old KPI
     warehouse after density fix; every navigation flickers stub

2) HAL MODEL CACHE WARM (REC-007 — ALREADY APPLIED)
   - apex_hal_cache_warm_pack.py; keep_alive=-1; GET/POST cache-warm APIs
   - Doc: MOONSHOT_REC007_HAL_CACHE_WARM_APPLIED_2026-07-12.md
   - Distinct from widget stub — do not confuse Ollama warm with mosaic

3) IMPORT / REPORTS BUNDLE CACHE + SoftDent SQLite
   - Prior WHY-ERRORS: SQLite lock → fallback to stale export cache
   - Collections/Daysheet gap still empty ≠ $0

4) BROWSER IndexedDB widget cache
   - idb.loadWidgets paints immediately; idb.cacheWidgets skips when warming
   - No buildId invalidation visible in load path — stale pre-10562 mosaics
     can flash or stick until network replaces them

OPERATOR SYMPTOM FRAME (infer honestly; do not invent unseen bugs):
After KPI density + stub fast-path, operators likely experience: blank/
"Loading bridge instruments" flash, stale many-KPI mosaic from IDB,
slow first paint, or HAL cold-start confusion. Name the MOST LIKELY
root cause(s) with file evidence; separate MUST vs SHOULD.

HONESTY: empty ≠ $0; no SoftDent write-back; real paths only.

OUTPUT (strict markdown — this IS the report):
# Verdict (one sentence — root cause + fix direction)
## 0. Operator Intent (quote verbatim; confirm consult-only; note cachi=cache)
## 1. Cache Map (layers + what each does)
## 2. Diagnosis (which layer is the problem; evidence; failure modes)
## 3. Fix Package (THE recommended work package)
Name, why now, effort, REAL files, phases, validation gate
## 4. What NOT to confuse / redo
## 5. Report Summary (executive bullets)
## 6. Approval checklist
DO NOT APPLY CODE. Prefer one clear fix package.
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

    excerpts: list[str] = []
    for name, lim in (
        ("MOONSHOT_KPI_DENSITY_FIX_APPLIED_2026-07-12.md", 1800),
        ("MOONSHOT_REC007_HAL_CACHE_WARM_APPLIED_2026-07-12.md", 1500),
        ("MOONSHOT_WHY_ERRORS_CONSULT_2026-07-12.md", 1800),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    backend = REPO / "NewRidgeFinancial2" / "apex_backend.py"
    core = REPO / "NewRidgeFinancial2" / "site" / "apex-core.js"
    snips = ""
    if backend.is_file():
        t = backend.read_text(encoding="utf-8")
        i = t.find("NR2_WIDGETS_STUB_FASTPATH")
        if i >= 0:
            snips += "### apex_backend stub fast-path\n```\n" + t[i - 200 : i + 900] + "\n```\n"
    if core.is_file():
        t = core.read_text(encoding="utf-8")
        i = t.find("Stale-while-revalidate")
        if i >= 0:
            snips += "### apex-core.js IDB + warming re-poll\n```\n" + t[i : i + 700] + "\n```\n"

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Ask Moonshot about the CACHE problem (cachi typo). Diagnose layers, "
        "prescribe ONE fix package, RE-REPORT. CONSULT ONLY — do not apply.\n\n"
        "Build: hal-10562. KPI density just shipped; stub-fastpath + IDB may "
        "still show old crowded KPIs or stuck warming-bridge.\n\n"
        + snips
        + "\n\n".join(excerpts)
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 8000,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Cache Problem Consult"
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
        f"# Moonshot AI — Cache Problem Diagnosis & Report (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** hal-10562 + hal-local:32b  \n"
        f"**Prior:** KPI density applied; REC-007 HAL warm applied; widget stub ON  \n"
        f"**Script:** `scripts/run_moonshot_cache_problem_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out = OUT / f"MOONSHOT_CACHE_PROBLEM_CONSULT_{DATE}.md"
    doc = DOCS / f"MOONSHOT_CACHE_PROBLEM_CONSULT_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    print(out)
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
