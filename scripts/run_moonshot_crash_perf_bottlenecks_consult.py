"""Moonshot AI — Crash / performance bottlenecks investigation (CONSULT ONLY).

Operator: find why application is crashing or performance bottlenecks;
report to Moonshot. Does NOT apply code.
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
    "find why my application is crashing or performance bottlenecks. "
    "to moonshot and report"
)

LIVE_EVIDENCE = """
LIVE PROBE (2026-07-13 ~16:50Z UTC) against https://127.0.0.1:8765/

PROCESS:
- TWO browser_app.py processes running (same StartTime 2026-07-13 11:47 local):
  PID 3188  WorkingSet ~146 MB  CPU ~180s  (main)
  PID 46060 WorkingSet ~4 MB    CPU ~0.02s (likely launcher/child or zombie sibling)
- No Python Application Error in Windows Event Log last 24h.
- SoftDent-adjacent: PWSvr.exe faulted 2026-07-12 13:11 local —
  Exception 0xc0000005 (access violation). Not NR2 Python crash.

HEALTH /api/health:
- ok=True db=True ollama=True importPipeline=True readinessLevel=fresh
- softdentOdbcMode=sensei+json-fallback softdentSdTablesPopulated=8
- lastOdbcExtract=2026-07-13T16:13:09+00:00
- /api/hal/status intermittent failure observed earlier in session
  (urllib error); not a process crash.

BUILD SKEW (still live):
- apex_backend.BUILD_ID = "hal-10608"
- /api/app-info schemaVersion = hal-10576 ; version=2.0
- site/index.html asset query + chrome chip still "hal-10576"
  (APPLIED doc claimed alignment to 10608 — chrome not fully converged)

WIDGET LATENCY (pass1, no Sync):
- financial: 29ms, 35 widgets, warm=False (cached)
- taxes/softdent/qb/ar/claims/narratives/documents/library/OM/hal:
  ~27–35ms each BUT warming-bridge only (background fill not done)
- Rapid poll financial x20: all HTTP 200, p50~9ms, max~32ms, NO 429
  (rate-limit exemption for /api/apex/widgets IS working)

SYNC RECOVERY:
- POST /api/apex/import/sync without proper path/token returned None/23ms
  (endpoint may differ); subsequent poll: warm 3/11 → 1/11 → 0/11 in ~6s
- fillFailed=False on all sampled pages (no fill-thread crash this probe)

PRIOR FIXED (do not re-diagnose as open):
- sqlite3.connect timeout=10 + PRAGMA busy_timeout=5000 in
  softdent_practice_exports.py (why-errors consult)
- MUST patches from page-smoke: widget rate-limit prefix exempt,
  apex-core 429 backoff + buildId skew reload, warming Cache-Control no-store

STILL OPEN PERF / UX:
- Stub-fastpath + background fill → mosaic shows warming-bridge until fill
  completes (feels like hang/crash to operator even though HTTP 200)
- Dual browser_app processes → possible port/cache contention
- schemaVersion/chrome still hal-10576 vs BUILD_ID hal-10608
- SHOULD Sync semaphore never applied (stampede risk after real Sync)
- Data gaps (GOLD_CSV_MISSING / ERA_835_REQUIRED) are honesty empties —
  not crashes; do not invent Gold

SMOKE CENSUS (warm, earlier today):
- 177 widgets · 138 working · 39 gap/empty/warn · 0 crashed widgets
"""

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL
(bridge telemetry BUILD_ID=hal-10608; UI chrome/schema still shows
hal-10576 — note skew).

OPERATOR INTENT: Find why the application is crashing OR where the
performance bottlenecks are. Produce a REPORT. CONSULT ONLY —
DO NOT claim you applied code. DO NOT invent SoftDent dollars / Gold /
ERA lines.

Separate clearly:
1) FATAL crashes (process die / Windows fault) vs recovered errors
2) Perceived "crash" (warming-bridge stall, blank mosaic, HAL chat gone)
3) True performance bottlenecks (fill thread, dual process, Sync stampede,
   SQLite locks — note locks already timeout-hardened)
4) Data honesty gaps (Gold/ERA) that are NOT crashes

Rank root causes by operator impact. Prefer additive fixes with REAL
files. If no code is justified, say so and give OPS-only next.

Already shipped (do NOT redo as primary package):
- SQLite timeout+busy_timeout in softdent_practice_exports.py
- /api/apex/widgets rate-limit exemption + apex-core 429 backoff
- warming Cache-Control no-store + X-NR2-Build-Id

REAL PATHS:
- NewRidgeFinancial2/browser_app.py
- NewRidgeFinancial2/apex_backend.py  (_WIDGETS_CACHE, stub fastpath,
  fillFailed, Sync clear)
- NewRidgeFinancial2/nr2_rate_limit.py
- NewRidgeFinancial2/nr2_http_server.py
- NewRidgeFinancial2/site/apex-core.js
- NewRidgeFinancial2/site/index.html  (still hal-10576 assets)
- NewRidgeFinancial2/softdent_practice_exports.py
- NewRidgeFinancial2/docs/MOONSHOT_APPLIED_PAGE_SMOKE_ANALYZE_REPAIRS_2026-07-13.md
- NewRidgeFinancial2/docs/MOONSHOT_WHY_ERRORS_CONSULT_2026-07-12.md

OUTPUT (strict markdown):
# Verdict (one sentence — crash vs bottleneck truth)
## 0. Operator Intent (verbatim; confirm consult-only)
## 1. Crash analysis (fatal vs perceived; evidence)
## 2. Performance bottlenecks (ranked; evidence; impact)
## 3. Recommended fix package (MUST / SHOULD / OPS — ranked)
## 4. Code patches (if any) — full unified diffs or complete functions
## 5. What NOT to redo / invent
## 6. Acceptance criteria + validation gate
## 7. Executive Summary (5 bullets)
## 8. Approval checklist
If the app is NOT crashing, say so bluntly and name the bottleneck.
"""


def _snip(path: Path, needle: str, before: int = 60, after: int = 500) -> str:
    if not path.is_file():
        return ""
    t = path.read_text(encoding="utf-8", errors="replace")
    i = t.find(needle)
    if i < 0:
        return ""
    start = max(0, i - before)
    return f"### {path.name} · `{needle}`\n```\n{t[start : i + after]}\n```\n"


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

    nr2 = REPO / "NewRidgeFinancial2"
    snips = ""
    snips += _snip(nr2 / "apex_backend.py", "NR2_WIDGETS_STUB_FASTPATH", 40, 900)
    snips += _snip(nr2 / "apex_backend.py", "_WIDGETS_FILL_FAILURES", 20, 200)
    snips += _snip(nr2 / "apex_backend.py", "_WIDGETS_CACHE.clear()", 80, 120)
    snips += _snip(nr2 / "nr2_rate_limit.py", "is_rate_limit_exempt", 40, 250)
    snips += _snip(nr2 / "softdent_practice_exports.py", "PRAGMA busy_timeout", 80, 80)

    core = nr2 / "site" / "apex-core.js"
    if core.is_file():
        t = core.read_text(encoding="utf-8", errors="replace")
        for needle in ("warmingPollStreak", "payload.warming", "fillFailed", "429"):
            i = t.find(needle)
            if i >= 0:
                snips += f"### apex-core.js · `{needle}`\n```\n{t[i : i + 450]}\n```\n"

    idx = nr2 / "site" / "index.html"
    if idx.is_file():
        t = idx.read_text(encoding="utf-8", errors="replace")
        snips += "### index.html (chrome / ASSET_V)\n```\n"
        for line in t.splitlines():
            if "hal-105" in line or "NR2_BUILD" in line or "ASSET_V" in line:
                snips += line.strip() + "\n"
        snips += "```\n"

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Investigate crashes and performance bottlenecks. CONSULT ONLY.\n"
        "If code patches are justified beyond already-shipped fixes, INCLUDE "
        "full unified diffs. Separate fatal crash from perceived hang from "
        "data gaps. Do not invent Gold/ERA dollars.\n\n"
        f"## LIVE EVIDENCE\n{LIVE_EVIDENCE}\n\n"
        f"## CODE EXCERPTS\n{snips}"
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
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Crash Perf Bottlenecks"
    import urllib.request

    print("Calling Moonshot AI (crash/perf bottlenecks — consult only)...")
    req = urllib.request.Request(
        base_url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            content = extract_message_content(json.loads(resp.read().decode()))
        status = "ok"
    except Exception as exc:  # noqa: BLE001
        content = str(exc)
        status = "error"

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    header = (
        f"# Moonshot AI — Crash / Performance Bottlenecks (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**UTC:** {stamp}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Bridge BUILD_ID:** hal-10608 (UI chrome may still show hal-10576)  \n"
        f"**Script:** `scripts/run_moonshot_crash_perf_bottlenecks_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves. If code is present "
        f"below, it is captured for review only.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out = OUT / f"moonshot_crash_perf_bottlenecks_{stamp}.md"
    doc = DOCS / f"MOONSHOT_CRASH_PERF_BOTTLENECKS_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    (OUT / f"moonshot_crash_perf_bottlenecks_{stamp}.json").write_text(
        json.dumps(
            {
                "status": status,
                "model": model,
                "operator": OPERATOR_REQUEST_VERBATIM,
                "chars": len(content or ""),
                "doc": str(doc),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(out)
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
