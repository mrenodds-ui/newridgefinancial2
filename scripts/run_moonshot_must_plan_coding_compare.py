"""Moonshot AI — Review our MUST apply plan; return correct coding (CONSULT ONLY).

Operator: give plan to moonshot and ask for code and compare then report.
Does NOT apply patches.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / ".local_logs" / "moonshot_financial_eval"
DOCS = REPO / "NewRidgeFinancial2" / "docs"
NR2 = REPO / "NewRidgeFinancial2"
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
    "now give plan to moonshot and ask for code and compare then report"
)

OUR_PLAN = r"""
# Our MUST apply plan (hal-10611) — validated against REAL repo

Scope: MUST only. SoftDent A/R = OPS (Excel/Print Preview). No invented APIs.

## Rejected from Moonshot's prior coding
- Wrong PIDFILE path `data/nr2-browser.pid` — REAL is `NewRidgeFinancial2/.nr2_browser_app.pid`
- `psutil` dependency — NOT in project; reject
- Invented `schedule_softdent_ar_refresh` — does not exist; reject
- Blanket `if not w.get("empty")` — wrong field; empties use `status=="empty"`; reject

## Our implementation plan
1) Align BUILD_ID / ASSET_V / nr2-build.json → **hal-10611**
2) Port-aware `ensure_singleton()` with REAL pidfile; stdlib/ctypes bind or port probe; NO psutil;
   rewrite pidfile to listening PID after bind
3) Financial empty-surface omit via **apex_compact_pages_pack** finalize chain
   (apply_collapse_empty_all → apply_kpi_density_contract), page=financial only;
   omit status==empty non-strip analysis/gap surfaces; empty ≠ $0
4) Tests test_hal10611_program_coherence.py + MOONSHOT_* applied doc + restart gates

Out of scope: SoftDent AR invent refresh, warming debounce new APIs, zero-scroll guarantee
"""

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL.

Operator sends OUR MUST APPLY PLAN for review and wants CORRECT CODING BACK.
Then we will compare your coding to the plan.

CONSULT ONLY — do not claim applied. empty ≠ $0. Never invent SoftDent dollars.
Real paths only. Do NOT invent psutil, schedule_softdent_ar_refresh, or wrong pidfile paths.
Do NOT invent modules that are not listed.

HARD CONSTRAINTS FROM OUR PLAN (honor):
- Ship target BUILD: **hal-10611**
- PIDFILE MUST remain: NewRidgeFinancial2/.nr2_browser_app.pid
- No new pip deps (no psutil)
- SoftDent A/R softGap = OPS desktop Excel/Print Preview only
- Financial omit uses status=="empty" + compact pack pipeline, NOT w.get("empty")
- Prefer surgical diffs against REAL file contents provided

YOUR JOB:
1) Accept/refine our plan (or refute with evidence)
2) Return FULL correct unified diffs that match REAL paths/code
3) Call out any disagreement with our plan explicitly
4) Validation gates

OUTPUT (strict markdown):
# Verdict (accept plan / revise plan — one sentence)
## 0. Operator Intent (verbatim; consult-only)
## 1. Plan review (agree / revise table vs our MUST plan)
## 2. Correct coding packages (MUST only for this ship)
## 3. Full unified diffs (real files only — complete patches)
## 4. Disagreements with Cursor plan (if any)
## 5. What NOT to invent
## 6. Acceptance criteria
## 7. Executive Summary (5 bullets)
## 8. Approval checklist
"""


def _excerpt(path: Path, start_needle: str, n_lines: int = 60) -> str:
    if not path.is_file():
        return f"(missing {path})"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for i, line in enumerate(lines):
        if start_needle in line:
            chunk = "\n".join(f"{i + j + 1}|{lines[i + j]}" for j in range(min(n_lines, len(lines) - i)))
            return f"### {path.relative_to(REPO)} (`{start_needle}`)\n```\n{chunk}\n```"
    return f"(needle missing in {path}: {start_needle})"


def _context() -> str:
    parts = [
        OUR_PLAN,
        _excerpt(NR2 / "nr2-build.json", "schemaVersion", 20),
        _excerpt(NR2 / "apex_backend.py", 'BUILD_ID = "', 8),
        _excerpt(NR2 / "site" / "apex-core.js", "ASSET_V = ", 12),
        _excerpt(NR2 / "browser_app.py", "PIDFILE = ", 90),
        _excerpt(NR2 / "apex_compact_pages_pack.py", "def apply_collapse_empty_all", 40),
        _excerpt(NR2 / "apex_compact_pages_pack.py", "def apply_kpi_density_contract", 50),
        _excerpt(NR2 / "apex_backend.py", "apply_collapse_empty_all", 25),
        _excerpt(NR2 / "desktop_app.py", "DESIGN_SCHEMA_VERSION", 15),
    ]
    # start script pid rewrite area
    parts.append(
        _excerpt(
            REPO / "scripts" / "start_nr2_browser.ps1",
            "Stop-AllBrowserAppProcesses",
            40,
        )
    )
    return "\n\n".join(parts)


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No API key", file=sys.stderr)
        return 1
    if "moonshot" in (base_url or "").lower():
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    else:
        model = str(
            os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2"
        ).strip()

    user = (
        f"Operator request (verbatim):\n> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"Our MUST plan + REAL code:\n{_context()}\n\n"
        "Return correct coding for this plan. Consult only."
    )

    payload = {
        "model": model,
        "temperature": 1.0 if "moonshot" in base_url.lower() else 0.2,
        "max_tokens": 14000,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    req = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://newridgefamilyfinancial.local",
            "X-Title": "NR2 Moonshot Plan Coding Compare",
        },
        method="POST",
    )
    print(f"key={key_name} model={model} base={base_url}", flush=True)
    try:
        with urllib.request.urlopen(req, timeout=700) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        print(f"HTTPError {e.code}: {e.read()[:800]}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1

    content = extract_message_content(body) or ""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = OUT / f"moonshot_plan_coding_raw_{stamp}.json"
    raw_path.write_text(
        json.dumps(
            {
                "model": model,
                "key": key_name,
                "operator": OPERATOR_REQUEST_VERBATIM,
                "content": content,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    moonshot_doc = DOCS / f"MOONSHOT_MUST_PLAN_CODING_RESPONSE_{DATE}.md"
    header = (
        f"# Moonshot AI — MUST plan coding response (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Ship target:** hal-10611\n"
        f"**Script:** `scripts/run_moonshot_must_plan_coding_compare.py`\n"
        f"**Apply:** DO NOT APPLY until comparison report + operator approve.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    moonshot_doc.write_text(header + content + "\n", encoding="utf-8")
    print(f"wrote {moonshot_doc}", flush=True)
    print(f"wrote {raw_path}", flush=True)

    # --- Comparison report (Cursor vs Moonshot) ---
    compare = _build_compare_report(content)
    compare_path = DOCS / f"MOONSHOT_MUST_PLAN_COMPARE_REPORT_{DATE}.md"
    compare_path.write_text(compare, encoding="utf-8")
    print(f"wrote {compare_path}", flush=True)
    preview = re.sub(r"[^\x00-\x7F]+", "?", content)[:4000]
    print("--- MOONSHOT PREVIEW ---", flush=True)
    print(preview, flush=True)
    print("--- COMPARE PREVIEW ---", flush=True)
    print(re.sub(r"[^\x00-\x7F]+", "?", compare)[:3500], flush=True)
    return 0


def _build_compare_report(moonshot: str) -> str:
    m = moonshot.lower()
    checks = [
        (
            "hal-10611 build bump",
            "hal-10611" in m and "nr2-build.json" in m,
            "Plan + Moonshot should both bump nr2-build.json / BUILD_ID / ASSET_V to hal-10611",
        ),
        (
            "Real PIDFILE path",
            ".nr2_browser_app.pid" in moonshot,
            "Must keep NewRidgeFinancial2/.nr2_browser_app.pid (reject data/nr2-browser.pid)",
        ),
        (
            "Wrong PIDFILE rejected",
            "data/nr2-browser.pid" not in moonshot
            and "data\\nr2-browser.pid" not in moonshot,
            "Moonshot must not re-introduce invented pidfile path",
        ),
        (
            "No psutil invent",
            "import psutil" not in moonshot and "pip install psutil" not in m,
            "Plan forbids new deps; port check via stdlib/ctypes only",
        ),
        (
            "No SoftDent invent scheduler",
            "schedule_softdent_ar_refresh" not in moonshot,
            "SoftDent A/R remains OPS desktop Excel/Print Preview",
        ),
        (
            "status==empty omit (not w.get empty)",
            'status' in m and ('"empty"' in moonshot or "status == \"empty\"" in moonshot or "status=='empty'" in moonshot or "status == 'empty'" in moonshot or 'status=="empty"' in moonshot),
            "Omit surfaces use status==empty via compact pack, not invent empty bool",
        ),
        (
            "compact pack / finalize chain",
            "apex_compact_pages_pack" in m or "apply_collapse_empty" in m or "apply_kpi_density" in m,
            "Wire through existing compact finalize helpers",
        ),
        (
            "unified diffs present",
            "```diff" in moonshot or "--- a/" in moonshot,
            "Moonshot should return concrete patches",
        ),
    ]

    rows = []
    agree = 0
    for name, ok, note in checks:
        if ok:
            agree += 1
            rows.append(f"| {name} | PASS | {note} |")
        else:
            rows.append(f"| {name} | FAIL / unclear | {note} |")

    verdict = (
        "Moonshot coding aligns with our MUST plan on hard constraints."
        if agree >= 6
        else "Moonshot coding partially conflicts — adapt before apply."
        if agree >= 4
        else "Moonshot coding diverges — prefer our plan surgical approach."
    )

    # Heuristic disagreements
    disagrees = []
    if "import psutil" in moonshot or "pip install psutil" in m:
        disagrees.append("- Reintroduces **psutil** (plan rejects).")
    if "schedule_softdent" in m:
        disagrees.append("- Reintroduces SoftDent invent scheduler.")
    if "data/nr2-browser.pid" in moonshot or "data\\nr2-browser.pid" in moonshot:
        disagrees.append("- Wrong PIDFILE path again.")
    if "w.get(\"empty\")" in moonshot or "not w.get('empty')" in moonshot:
        disagrees.append("- Uses invent/`empty` bool filter instead of `status==\"empty\"`.")
    if not disagrees:
        disagrees.append("- No hard-constraint violations detected in automated scan.")

    return f"""# Moonshot MUST plan — compare report (CONSULT ONLY)

**Date:** {DATE}  
**Plan:** hal-10611 MUST (build skew + port-aware singleton + financial empty omit)  
**Moonshot response:** `MOONSHOT_MUST_PLAN_CODING_RESPONSE_{DATE}.md`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)
> {OPERATOR_REQUEST_VERBATIM}

## Verdict
{verdict} Automated constraint score: **{agree}/{len(checks)}**.

## Constraint comparison

| Check | Result | Note |
|-------|--------|------|
{chr(10).join(rows)}

## Plan vs Moonshot — side-by-side

| Topic | Cursor plan | Moonshot coding response |
|-------|-------------|--------------------------|
| Build | bump to **hal-10611** across apex / JS / nr2-build.json | See response §2–3 |
| Singleton | REAL `.nr2_browser_app.pid`; port-aware; no psutil; rewrite listener PID | See response singleton patch |
| Financial omit | compact pack finalize; `status==\"empty\"` analysis surfaces | See response financial omit patch |
| SoftDent A/R | OPS Excel/Print Preview only | Must remain OPS (not code-invent) |
| Tests | test_hal10611_program_coherence.py | Expect Moonshot to keep/extend |

## Hard disagreements / invent flags
{chr(10).join(disagrees)}

## Recommended apply path (after approval)
1. Prefer **our plan structure** as the scaffold (real paths, no new deps).
2. Adopt Moonshot **diff hunks that pass the constraint table**.
3. Discard any Moonshot hunk that invents deps/APIs/wrong pidfile/`empty` bool filter.
4. Ship as **hal-10611**, restart, gate `/api/app-info` + taxes strip + financial empty omit.

## Approval checklist
- [ ] Constraint score acceptable (≥6/8 or discrepancies explained)
- [ ] Approve apply of merged MUST package
- [ ] SoftDent A/R OPS acknowledged separately
- [ ] Restart + live gates after apply

## Sources
- Plan: `.cursor/plans/moonshot_program_must_plan_96cd9264.plan.md`
- Moonshot coding: `NewRidgeFinancial2/docs/MOONSHOT_MUST_PLAN_CODING_RESPONSE_{DATE}.md`
- Prior consult: `MOONSHOT_FULL_PROGRAM_CODING_CONSULT_{DATE}.md`
"""


if __name__ == "__main__":
    raise SystemExit(main())
