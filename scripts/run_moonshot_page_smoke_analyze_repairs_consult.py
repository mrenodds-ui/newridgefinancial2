"""Moonshot AI — Page-by-page smoke analyze + repairs (CONSULT ONLY).

Operator: send smoke findings for analyze and repairs / recommendations.
Consult only. If Moonshot supplies code patches, capture them in the doc —
do NOT apply until operator approves.
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
    "send to moonshot for analyze and repairs, recommendations consult only "
    "if he has code get it"
)

SYSTEM = """You are Moonshot AI — principal engineer for NR2 Apex HAL
(bridge telemetry HAL-10608; UI chip still shows hal-10576 — note skew).

OPERATOR INTENT (verbatim below): Analyze the live page-by-page smoke report,
recommend repairs, CONSULT ONLY. If you have concrete code patches that fix
the repairable items, INCLUDE FULL UNIFIED DIFFS or complete replacement
functions in the report so the operator can apply later. DO NOT claim you
applied code. DO NOT invent SoftDent dollars / Gold lines / Excel from
Print Preview.

LIVE SMOKE VERDICT (warm mosaic census, then Sync+poll degraded):
- When warm: 177 widgets total · 138 working · 39 data-gap/empty/warn · 0 crashed
- All 11 pages + subpages navigate; Compact/Mute/Ask HAL chrome work
- HAL POST /api/apex/hal/orchestrate with X-NR2-Session-Token → 200 (chat8b/reason21b)
- Without token → 403 browser_mutation_forbidden (expected)
- Sync clears _WIDGETS_CACHE → all pages return warming-bridge
- Aggressive /api/apex/widgets/* polling → HTTP 429 rate_limited → mosaic stuck
  on warming-bridge for prolonged period (HAL chat prompts disappear)
- Gold still GOLD_CSV_MISSING (paymentLines=0); ERA_835_REQUIRED collections;
  CLAIMS_AR_RECONCILE_MISMATCH claims=61
- PRODBYADA HAL-10609 OK (not Gold); print-preview audit HAL-10590 honesty OK

PAGE COUNTS (warm):
financial 35 (31/4), taxes 9 (8/1), softdent 31 (24/7), quickbooks 9 (9/0),
ar 13 (11/2), claims 18 (12/6), narratives 5 (3/2), documents 5 (4/1),
library 3 (1/2), office-manager 34 (22/12), hal 15 (13/2)

CRITICAL GAPS (honesty — not invent):
- softdent-gold-payment-pipeline / gold-csv-drop-ops: GOLD_CSV_MISSING
- softdent-collections-gap / claims ERA / import-health: ERA_835_REQUIRED
- softdent-outstanding-claims-bridge: CLAIMS_AR_RECONCILE_MISMATCH
- Many empty UI cards (dossier, forecast, denial pareto, lib-storage, OM cards)

YOUR JOB:
1) Separate REPAIRABLE code/UX bugs from OPS/data blockers (Gold CSV, ERA).
2) Rank a SHORT repair package (MUST then SHOULD) that improves operator UX
   without inventing Gold.
3) For MUST code repairs: ship real patches against REAL files listed below
   (unified diff preferred). Focus likely: widget rate-limit exemption /
   Sync→warm coherence / stuck warming after 429 / buildId chrome skew.
4) OPS recommendations only for Gold/ERA — exact SoftDent steps if needed;
   do not invent CSV contents.
5) Do NOT redo: Gold invent from Print Preview, money invent, SoftDent write-back.

REAL PATHS:
- NewRidgeFinancial2/apex_backend.py  (build_apex_widgets stub, Sync clears cache)
- NewRidgeFinancial2/nr2_rate_limit.py  (RATE_LIMIT_EXEMPT_PATHS — widgets NOT exempt)
- NewRidgeFinancial2/nr2_http_server.py  (429 abort)
- NewRidgeFinancial2/nr2_browser_security.py  (mutation token)
- NewRidgeFinancial2/site/apex-core.js  (warming re-poll / IDB)
- NewRidgeFinancial2/docs/_nr2_page_smoke_report.json
- canvases/nr2-page-by-page-smoke.canvas.tsx (operator canvas)

OUTPUT (strict markdown):
# Verdict (one sentence)
## 0. Operator Intent (quote verbatim; confirm consult-only)
## 1. Analyze — Working vs Not (code bugs vs OPS/data)
## 2. Recommended Repair Package (MUST / SHOULD / OPS — ranked)
## 3. Code Patches (if any) — full unified diffs or complete functions
## 4. What NOT to do / invent
## 5. Acceptance criteria + validation gate
## 6. Executive Summary (5 bullets)
## 7. Approval checklist (operator must approve before apply)
If no code is justified yet, say so explicitly and give OPS-only next.
"""


def _snip(path: Path, needle: str, before: int = 80, after: int = 700) -> str:
    if not path.is_file():
        return ""
    t = path.read_text(encoding="utf-8")
    i = t.find(needle)
    if i < 0:
        return ""
    start = max(0, i - before)
    return f"### {path.name} · `{needle}`\n```\n{t[start : i + after]}\n```\n"


def _smoke_summary() -> str:
    p = DOCS / "_nr2_page_smoke_report.json"
    if not p.is_file():
        return "(smoke JSON missing)"
    data = json.loads(p.read_text(encoding="utf-8"))
    lines = [
        f"working={data.get('working')} gap={data.get('gap_n')} broken={data.get('broken_n')}",
        "pages:",
    ]
    for page, info in (data.get("pages") or {}).items():
        lines.append(f"  {page}: n={info.get('n')} by={info.get('by')}")
    lines.append("gaps:")
    for g in (data.get("gap") or [])[:40]:
        lines.append(
            f"  {g.get('page')}\t{g.get('id')}\t{g.get('status')}\t"
            f"{g.get('gapCode')}\t{(g.get('msg') or '')[:100]}"
        )
    lines.append("apis:")
    for a in data.get("apis") or []:
        lines.append(
            f"  {a.get('method')} {a.get('path')} http={a.get('http')} ok={a.get('ok')}"
        )
    return "\n".join(lines)


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
    snips += _snip(nr2 / "apex_backend.py", "_WIDGETS_CACHE.clear()", 120, 200)
    snips += _snip(nr2 / "nr2_rate_limit.py", "RATE_LIMIT_EXEMPT_PATHS", 20, 400)
    snips += _snip(nr2 / "nr2_http_server.py", "rate_limited", 120, 200)

    core = nr2 / "site" / "apex-core.js"
    if core.is_file():
        t = core.read_text(encoding="utf-8")
        for needle in ("warming", "Stale-while-revalidate", "loadWidgets"):
            i = t.lower().find(needle.lower()) if needle != "warming" else t.find("payload.warming")
            if i < 0 and needle == "warming":
                i = t.find("warming")
            if i >= 0:
                snips += f"### apex-core.js · `{needle}`\n```\n{t[i : i + 500]}\n```\n"
                break

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Analyze the page-by-page smoke. Recommend repairs. CONSULT ONLY.\n"
        "If you have code patches for repairable bugs, INCLUDE them (full diffs).\n"
        "Do not invent Gold/ERA dollars. Separate code UX fixes from OPS blockers.\n\n"
        "## Smoke summary\n"
        f"{_smoke_summary()}\n\n"
        "## Code excerpts\n"
        f"{snips}"
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
        headers["X-Title"] = "NR2 Page Smoke Analyze Repairs"
    import urllib.request

    print("Calling Moonshot AI (page smoke analyze/repairs — consult only)...")
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
        f"# Moonshot AI — Page-by-Page Smoke Analyze & Repairs (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**UTC:** {stamp}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Bridge:** HAL-10608 (UI chip may still show hal-10576)  \n"
        f"**Script:** `scripts/run_moonshot_page_smoke_analyze_repairs_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves. If code is present below, "
        f"it is captured for review only.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out = OUT / f"moonshot_page_smoke_analyze_repairs_{stamp}.md"
    doc = DOCS / f"MOONSHOT_PAGE_SMOKE_ANALYZE_REPAIRS_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    (OUT / f"moonshot_page_smoke_analyze_repairs_{stamp}.json").write_text(
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
