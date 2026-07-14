"""Moonshot AI — Import cache KPIs not loading (CONSULT ONLY).

Operator: ask moonshot the import kache - kpi are not loading consult
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

OPERATOR_REQUEST_VERBATIM = "ask moonshot the import kache - kpi are not loading consult"

LIVE_EVIDENCE = """
LIVE PROBE https://127.0.0.1:8765/ (2026-07-13 ~17:20Z)

HEALTH:
- ok=True db=True importPipeline=True readinessLevel=fresh
- import_bundle_age_minutes=0
- softdentOdbcMode=sensei+json-fallback
- app-info schemaVersion=hal-10608 assetVersion=hal-10608 (aligned)

INSTANT WIDGET SNAPSHOT (coldish):
- financial: 35 widgets OK (cached)
- softdent / ar / quickbooks: warming-bridge only (message:
  "Warming import cache — KPIs appear when ready (empty ≠ $0).")
- claims: 18 OK; taxes: 9 OK

POLLED RECOVERY (4s cadence, 6 pages):
t+0s  softdent OK31 | ar OK13 | qb OK9 | financial W | OM W | docs W
t+4s  softdent OK31 | ar W | qb W | financial W | OM OK34 | docs OK5
t+8s  all OK (financial 35, ar 13, qb 9, softdent 31, OM 34, docs 5)

INTERPRETATION (for Moonshot to confirm/refute):
- KPIs are NOT permanently broken; import cache fill eventually succeeds.
- Operator sees "not loading" because stub-fastpath returns warming-bridge
  immediately while background _fill runs; pages rotate W↔OK as 15s TTL
  expires and concurrent page fills contend for _load_reports_and_bundle /
  fill thread.
- fillProgress often stays 0 for waiting pages because _FILL_PROGRESS is
  single global keyed by one page at a time — other pages look stuck at 0%.
- No fillFailed observed; no Widget cache fill failed in server log.
- Rate-limit exemption for /api/apex/widgets already shipped (no 429).
- Sync semaphore already shipped (423 when Sync held).

ALREADY SHIPPED (do not redo as primary):
- Widget rate-limit prefix exempt + client 429 backoff
- warming Cache-Control no-store + buildId skew reload
- crash/perf singleton + Sync 423 + fillProgress telemetry (partial)
- SQLite busy_timeout on practice exports

LIKELY OPEN CODE UX (Moonshot to rank):
1) Concurrent page stampede after TTL — many warming fills at once
2) Single global _FILL_PROGRESS (wrong page shows 0%)
3) Warming stub lacks per-page queue / Retry-After semantics
4) _REPORTS_BUNDLE_CACHE TTL 20s vs _WIDGETS_CACHE 15s coherence
5) Operator messaging: warming ≠ crash / empty ≠ $0
"""

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL
(BUILD_ID=hal-10608).

OPERATOR: import cache KPIs are not loading — CONSULT ONLY.
Do NOT claim you applied code. Do NOT invent SoftDent dollars / Gold / ERA.

Focus on the LIVE evidence: warming-bridge stub while background fill runs;
pages flip W↔OK over ~8s; fillProgress=0 on waiting pages; health/import
pipeline fresh. Separate:
- permanent failure vs perceived hang
- import cache / stub-fastpath / fill contention vs data honesty gaps
- already-shipped fixes vs remaining MUST/SHOULD

REAL PATHS:
- NewRidgeFinancial2/apex_backend.py  (build_apex_widgets stub, _WIDGETS_CACHE,
  _FILL_PROGRESS, _REPORTS_BUNDLE_CACHE, _load_reports_and_bundle)
- NewRidgeFinancial2/site/apex-core.js  (warming poll / fillProgress log)
- NewRidgeFinancial2/import_loader.py
- NewRidgeFinancial2/nr2_rate_limit.py  (widgets exempt — already shipped)
- NewRidgeFinancial2/docs/MOONSHOT_APPLIED_CRASH_PERF_BOTTLENECKS_2026-07-13.md
- NewRidgeFinancial2/docs/MOONSHOT_APPLIED_PAGE_SMOKE_ANALYZE_REPAIRS_2026-07-13.md

OUTPUT (strict markdown):
# Verdict (one sentence)
## 0. Operator Intent (verbatim; confirm consult-only)
## 1. Why KPIs look not loading (ranked root causes + evidence)
## 2. Permanent vs transient (what staff should do NOW)
## 3. Recommended fix package (MUST / SHOULD / OPS — ranked)
## 4. Code patches (if any) — full unified diffs or complete functions
## 5. What NOT to redo / invent
## 6. Acceptance criteria + validation gate
## 7. Executive Summary (5 bullets)
## 8. Approval checklist
Prefer additive UX/coherence fixes. empty ≠ $0. No SoftDent write-back.
"""


def _snip(path: Path, needle: str, before: int = 40, after: int = 700) -> str:
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
    snips += _snip(nr2 / "apex_backend.py", "NR2_WIDGETS_STUB_FASTPATH", 40, 1100)
    snips += _snip(nr2 / "apex_backend.py", "_FILL_PROGRESS", 20, 200)
    snips += _snip(nr2 / "apex_backend.py", "def _load_reports_and_bundle", 20, 450)
    snips += _snip(nr2 / "apex_backend.py", "_WIDGETS_CACHE_TTL_SEC", 10, 80)
    snips += _snip(nr2 / "site" / "apex-core.js", "fillProgress", 40, 350)

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Diagnose why import-cache KPIs appear not loading. CONSULT ONLY.\n"
        "If code patches are justified, INCLUDE full diffs. Separate warming "
        "UX from Gold/ERA honesty gaps. Do not invent dollars.\n\n"
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
        headers["X-Title"] = "NR2 Import Cache KPIs Not Loading"
    import urllib.request

    print("Calling Moonshot AI (import cache KPIs — consult only)...")
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
        f"# Moonshot AI — Import Cache KPIs Not Loading (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**UTC:** {stamp}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** hal-10608  \n"
        f"**Script:** `scripts/run_moonshot_import_cache_kpis_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out = OUT / f"moonshot_import_cache_kpis_{stamp}.md"
    doc = DOCS / f"MOONSHOT_IMPORT_CACHE_KPIS_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    (OUT / f"moonshot_import_cache_kpis_{stamp}.json").write_text(
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
