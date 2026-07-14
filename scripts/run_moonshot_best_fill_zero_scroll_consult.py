"""Moonshot AI — Best widgets to FILL the page with ZERO scroll (CONSULT ONLY).

Operator: ok without scrolling and using the best widgets that fill the page
ask moonshoot ai how and what would he use
"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
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

CTX = ssl._create_unverified_context()
BASE = os.getenv("NR2_BROWSER", "https://127.0.0.1:8765").rstrip("/")

OPERATOR_REQUEST_VERBATIM = (
    "ok without scrolling and using the best widgets that fill the page "
    "ask moonshoot ai how and what would he use"
)

PRIOR = DOCS / "MOONSHOT_WIDGETS_SUCK_ZERO_SCROLL_CONSULT_2026-07-13.md"

SYSTEM = """You are Moonshot AI — principal UI/data architect for NR2 Apex HAL
(BUILD **hal-10611**).

Operator asks: WITHOUT SCROLLING, using the BEST widgets that FILL the page —
HOW and WHAT would YOU use?

CONSULT ONLY — do not claim applied. empty ≠ $0. Never invent SoftDent dollars.
Prefer REAL existing apex-core.js / apex_compact_pages_pack primitives over inventing
new chart libraries.

Prior consult (widgets suck) concluded PARTIAL: swap shells to compact contract,
demote ~70% to subpages/drawers; cannot keep all widgets above fold.

NOW sharpen: design the IDEAL zero-scroll FIRST VIEWPORT composition —
widgets that FILL the available space beautifully (not sparse leftovers, not cramped spam).
"Best" = high signal, dense, practice-truthful, import-backed when possible.

HARD CONSTRAINTS:
- 1920×1080 compact density; page scrollHeight ≈ viewport (±5px)
- Caps: micro≤120, secondary≤240, primary≤320 (or a single composed row that tiles horizontally)
- KPI budget ≤4 pills above fold
- HAL chat must remain usable if on that page
- Do not break Sync, authenticity of empty, SoftDent Excel/Print Preview OPS when needed
- Reuse existing types: executive-strip, financial-command-strip, radial-gauge,
  timeline-lanes, status-matrix, data-table (5-row), dual-axis-trend, horizontal-bar,
  bullet, waterfall (demoted), patient-dossier-card, action-list, etc.

YOUR JOB — pick YOUR best lineup:
1) The compact composition model (how the page fills: grid/mosaic/strip+tiles)
2) Exact widget set YOU would put ABOVE THE FOLD on each main page
3) What goes ONE click away (drawer/subpage) so first viewport stays filled but calm
4) Wireframe-style layout description (rows/cols + height budget)
5) Coding package if approved later (MUST/SHOULD, real paths)
6) Acceptance: no page scroll + first viewport feels full (not empty padding)

OUTPUT (strict markdown):
# Verdict (Moonshot's zero-scroll composition approach — one sentence)
## 0. Operator Intent (verbatim; consult-only)
## 1. How I would fill the page (composition model)
## 2. The best widgets I would USE (shared kit — ranked, why each)
## 3. Per-page first-viewport lineup (exact widgets + layout budget)
## 4. Demotion map (what leaves the first viewport)
## 5. Visual density rules (fill without scroll or sparseness)
## 6. Coding package if approved (MUST / SHOULD; real files)
## 7. Breakage risks
## 8. What NOT to invent / redo
## 9. Acceptance criteria
## 10. Executive Summary (5 bullets)
## 11. Approval checklist
Be concrete and opinionated — YOUR picks, not a laundry list.
"""


def get_json(path: str, timeout: int = 90):
    try:
        with urllib.request.urlopen(BASE + path, context=CTX, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        return {"error": type(e).__name__, "msg": str(e)[:160]}


def live() -> str:
    info = get_json("/api/app-info", 15)
    census = get_json("/api/apex/widget-census", 90)
    pages = {}
    for page in ("financial", "softdent", "claims", "taxes", "ar", "office-manager", "hal"):
        d = get_json(f"/api/apex/widgets/{page}", 90)
        if not isinstance(d, dict) or d.get("error"):
            pages[page] = d
            continue
        widgets = [w for w in (d.get("widgets") or []) if isinstance(w, dict)]
        pages[page] = {
            "buildId": d.get("buildId"),
            "n": len(widgets),
            "ids": [w.get("id") for w in widgets[:20]],
            "types": {},
        }
        for w in widgets:
            t = str(w.get("type") or "?")
            pages[page]["types"][t] = pages[page]["types"].get(t, 0) + 1
    prior = ""
    if PRIOR.is_file():
        prior = PRIOR.read_text(encoding="utf-8", errors="replace")[:4500]
    snap = {
        "schema": info.get("schemaVersion") if isinstance(info, dict) else None,
        "census": [
            {
                "page": p.get("page"),
                "total": p.get("total"),
                "withData": p.get("withData"),
                "empty": p.get("empty"),
            }
            for p in ((census or {}).get("pages") or [])
            if isinstance(p, dict)
        ],
        "pages": pages,
    }
    (OUT / "moonshot_best_fill_live.json").write_text(json.dumps(snap, indent=2), encoding="utf-8")
    return (
        "### Live\n```json\n"
        + json.dumps(snap, indent=2)[:10000]
        + "\n```\n\n### Prior widgets-suck verdict (excerpt)\n"
        + prior
    )


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
        f"{live()}\n\n"
        "Tell me HOW you would compose zero-scroll pages and WHAT best widgets YOU would use "
        "to fill the first viewport. Consult only."
    )
    payload = {
        "model": model,
        "temperature": 1.0 if "moonshot" in base_url.lower() else 0.2,
        "max_tokens": 11000,
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
            "X-Title": "NR2 Moonshot Best Fill Zero-Scroll",
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
    raw = OUT / f"moonshot_best_fill_raw_{stamp}.json"
    raw.write_text(
        json.dumps(
            {"model": model, "key": key_name, "operator": OPERATOR_REQUEST_VERBATIM, "content": content},
            indent=2,
        ),
        encoding="utf-8",
    )
    doc = DOCS / f"MOONSHOT_BEST_FILL_ZERO_SCROLL_CONSULT_{DATE}.md"
    header = (
        f"# Moonshot AI — Best widgets to fill page (zero-scroll) CONSULT ONLY\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Build:** hal-10611\n"
        f"**Script:** `scripts/run_moonshot_best_fill_zero_scroll_consult.py`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    doc.write_text(header + content + "\n", encoding="utf-8")
    print(f"wrote {doc}", flush=True)
    print(f"wrote {raw}", flush=True)
    print("--- PREVIEW ---", flush=True)
    print(re.sub(r"[^\x00-\x7F]+", "?", content)[:6000], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
