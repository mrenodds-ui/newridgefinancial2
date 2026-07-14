"""Moonshot AI — Why is NR2 throwing errors (CONSULT ONLY → REPORT).

Operator: ask moonshot why this program is throwing errors an report.
Does NOT apply code. Produces root-cause report with REAL paths.
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
    "ask moonshot why this program is throwing errors an report"
).strip()

LIVE_ERRORS = """
LIVE RUNTIME (browser_app.py @ https://127.0.0.1:8765/, schema logged as
hal-10550 on this process start; nr2-build.json currently hal-10561):

Repeated during cache warm / direct import assemble (3+ times same stack):

  Direct import pipeline unavailable; falling back to legacy fetch
  Traceback (most recent call last):
    File ".../practice_source_access.py", line 195, in assemble_direct_import_sections
      sd_pipe = build_softdent_pipeline_datasets()
    File ".../import_direct_pipeline.py", line 413, in build_softdent_pipeline_datasets
      practice = build_practice_pipeline_datasets()
    File ".../import_direct_pipeline.py", line 298, in build_practice_pipeline_datasets
      return read_practice_export_datasets()
    File ".../softdent_practice_exports.py", line 379, in read_practice_export_datasets
      np_rows = _aggregate_new_patients(conn, periods)
    File ".../softdent_practice_exports.py", line 70, in _aggregate_new_patients
      if not _table_exists(conn, table):
    File ".../softdent_practice_exports.py", line 27, in _table_exists
      cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
  sqlite3.OperationalError: database is locked

Code facts:
- softdent_practice_exports.py connects with sqlite3.connect(db_path) at lines
  377, 709, 862 — NO timeout=, NO PRAGMA busy_timeout.
- nr2_local_db.py / apex_unified_db_pack.py use timeout=10 elsewhere.
- assemble_direct_import_sections catches the exception, logs
  "Direct import pipeline unavailable; falling back to legacy fetch",
  and continues — so the app stays up but staff see noisy tracebacks and
  lose the direct SoftDent practice pipeline for that warm/load cycle.
- Health monitor later: ok=True reason=escalate30b (HAL path itself up).

Also known (do not confuse with this traceback):
- HAL 190Q quality/latency issues (Phase 1+2 applied; Phase 3 streaming open)
  — separate from this sqlite lock stack.
- Collections/Daysheet export gap (empty revenue-composition) — data gap,
  not this OperationalError.
"""

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex
(hal-10561 + SoftDent/QB local HTTPS bridge + HAL local 32B).

Operator asked WHY this program is throwing errors and wants a REPORT.
CONSULT ONLY — DO NOT claim you applied code. Do not invent PHI/dollars.

Focus on LIVE ERRORS first (sqlite database is locked during SoftDent
practice exports / direct import). Separate:
- fatal vs recovered (fallback) errors
- root cause vs symptom (traceback noise)
- concurrency / SQLite locking vs logic bugs
- what is already mitigated by legacy fallback
- what still hurts staff (logs, stale data, cold load)

REAL paths only:
- NewRidgeFinancial2/softdent_practice_exports.py
- NewRidgeFinancial2/practice_source_access.py
- NewRidgeFinancial2/import_direct_pipeline.py
- NewRidgeFinancial2/nr2_local_db.py
- NewRidgeFinancial2/apex_unified_db_pack.py
- NewRidgeFinancial2/browser_app.py
- Prefer additive fixes; empty ≠ $0; no SoftDent write-back

OUTPUT (strict markdown):
# Verdict (one sentence — primary why)
## 0. Operator Intent (verbatim)
## 1. What's Throwing (ranked; blunt) — each: error, severity, evidence, root cause
## 2. Why Now (concurrency / connect flags / callers)
## 3. Impact on staff / data honesty
## 4. Fix Package (ordered; REAL files; validation gate) — CONSULT ONLY
## 5. What NOT to confuse with these errors (already fixed / other tracks)
## 6. Executive Summary (5 bullets)
## 7. Approval checklist
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

    excerpts: list[str] = []
    for name in (
        "MOONSHOT_WHATS_WRONG_CONSULT_2026-07-10.md",
        "MOONSHOT_HAL_190Q_FIX_CONSULT_2026-07-12.md",
        "MOONSHOT_HAL_190Q_WHATS_NEXT_2026-07-12.md",
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:3500]}")

    # Attach relevant source snippets
    src_bits: list[str] = []
    for rel, start, end in (
        ("NewRidgeFinancial2/softdent_practice_exports.py", 19, 35),
        ("NewRidgeFinancial2/softdent_practice_exports.py", 370, 390),
        ("NewRidgeFinancial2/practice_source_access.py", 180, 260),
        ("NewRidgeFinancial2/nr2_local_db.py", 25, 40),
    ):
        path = REPO / rel
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        chunk = "\n".join(
            f"{i+1}|{lines[i]}" for i in range(start - 1, min(end, len(lines)))
        )
        src_bits.append(f"### {rel}:{start}-{end}\n```python\n{chunk}\n```")

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Produce a WHY-ERRORS REPORT. CONSULT ONLY.\n\n"
        f"## LIVE ERRORS\n{LIVE_ERRORS}\n\n"
        "## SOURCE SNIPPETS\n"
        + "\n\n".join(src_bits)
        + "\n\n## PRIOR CONSULT EXCERPTS\n"
        + "\n\n".join(excerpts)
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 9000,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Why Errors Consult"
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
        f"# Moonshot AI — Why This Program Is Throwing Errors (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** hal-10561 (process start logged hal-10550)  \n"
        f"**Primary live error:** `sqlite3.OperationalError: database is locked`  \n"
        f"**Script:** `scripts/run_moonshot_why_errors_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out = OUT / f"MOONSHOT_WHY_ERRORS_CONSULT_{DATE}.md"
    doc = DOCS / f"MOONSHOT_WHY_ERRORS_CONSULT_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    print(out)
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
