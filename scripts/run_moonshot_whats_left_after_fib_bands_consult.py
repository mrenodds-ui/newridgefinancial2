"""Moonshot AI — What's left on Apex pages after Fibonacci bands (CONSULT ONLY).

Operator: now ask moonshot what to do with what we have left of the pages
"""

from __future__ import annotations

import json
import os
import ssl
import sys
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

CTX = ssl._create_unverified_context()
BASE = os.getenv("NR2_BROWSER", "https://127.0.0.1:8765").rstrip("/")

OPERATOR_REQUEST_VERBATIM = (
    "now ask moonshot what to do with what we have left of the pages"
)

SYSTEM = """You are Moonshot AI — principal UI/data architect for NR2 Apex HAL
(BUILD **hal-10617** just shipped).

Operator asks: WHAT TO DO WITH WHAT WE HAVE LEFT OF THE PAGES?

CONSULT ONLY — do not claim applied. empty ≠ $0. Never invent SoftDent dollars.
Desktop SoftDent Excel/Print Preview remains period-close truth when needed.

JUST SHIPPED (hal-10617 on fix/main-validate-ci):
- Fibonacci mosaic bands: stage is flex rows (micro 80 / secondary 240 / primary 320)
- Widgets tile edge-to-edge (tile-50 / tile-33 / tile-100) via mosaicLayout
- Overview/Ops still capped ~≤5 tiles; chronic empty SoftDent-source widgets omitted
- Unlinked apex-theme.css + apex-mobile-polish.css (polish-only)
- SoftDent money-first keep: sd-vitals, collections-gauge, collections-gap,
  outstanding-claims-bridge, sd-prod-trend

PRIOR COMPACT STACK: hal-10610..10616 zero-scroll remap, omit empties, demote to Ops.

LIVE STATE is attached JSON (main + ops bands/ids + census). Treat that as truth
for "what we have left" — not the older Moonshot ideal lineups that still named
omitted widgets (ERA gauge, denial pareto, gold CSV OPS on main, overview kanban).

YOUR JOB — be opinionated about THE LEFTOVERS:
1) Verdict: are the pages "done enough" for staff, or still uneven?
2) Per page: what's GOOD to keep vs what's still awkward leftover (ops chips,
   spare micro bands, thin singles, narratives/documents/library if sparse)
3) ONE best NEXT package (not a laundry list) — highest ROI for what remains
4) Runner-ups (2–3) with why-not-now
5) SoftDent/Money honesty gaps that still need OPS pulls (not fake $)
6) What NOT to redo (bands rewrite, invent widgets, restore deleted theme, etc.)

OUTPUT (strict markdown):
# Verdict (one sentence — what to do with the leftovers)
## 0. Operator Intent (verbatim; consult-only)
## 1. Read of current pages (what's left / quality of fill)
## 2. Per-page leftovers (keep / fix / demote / OPS)
## 3. Recommended NEXT (name, why now, effort, REAL files, validation gate)
## 4. Why this beats other candidates now
## 5. Runner-ups (2–3)
## 6. SoftDent / import honesty still open
## 7. What NOT to redo
## 8. Acceptance criteria
## 9. Executive Summary (5 bullets)
## 10. Approval checklist
DO NOT APPLY CODE.
"""


def get_json(path: str, timeout: int = 90):
    try:
        with urllib.request.urlopen(BASE + path, context=CTX, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        return {"error": type(e).__name__, "msg": str(e)[:160]}


def live_snapshot() -> str:
    sys.path.insert(0, str(NR2))
    live: dict = {
        "buildExpected": "hal-10617",
        "operatorAsk": OPERATOR_REQUEST_VERBATIM,
        "lastCommitHint": "f01d89e Fibonacci bands",
    }
    try:
        from apex_backend import BUILD_ID

        live["buildId"] = BUILD_ID
    except Exception as exc:  # noqa: BLE001
        live["buildIdError"] = f"{type(exc).__name__}:{exc}"

    live["appInfo"] = get_json("/api/app-info", 15)
    census = get_json("/api/apex/widget-census", 90)
    if isinstance(census, dict) and not census.get("error"):
        live["census"] = {
            "pages": [
                {
                    "page": p.get("page"),
                    "total": p.get("total"),
                    "withData": p.get("withData"),
                    "empty": p.get("empty"),
                }
                for p in (census.get("pages") or [])
                if isinstance(p, dict)
            ][:20]
        }

    pages = {}
    for page in (
        "financial",
        "taxes",
        "softdent",
        "claims",
        "ar",
        "quickbooks",
        "office-manager",
        "hal",
        "narratives",
        "documents",
    ):
        d = get_json(f"/api/apex/widgets/{page}", 90)
        if not isinstance(d, dict) or d.get("error"):
            pages[page] = d
            continue
        widgets = [w for w in (d.get("widgets") or []) if isinstance(w, dict)]
        bands = ((d.get("mosaicLayout") or {}).get("bands")) or []
        pages[page] = {
            "buildId": d.get("buildId"),
            "n": len(widgets),
            "ids": [w.get("id") for w in widgets],
            "sizes": {w.get("id"): w.get("size") for w in widgets},
            "bands": [
                {
                    "band": b.get("band"),
                    "height": b.get("height"),
                    "tiles": [
                        {"id": t.get("id"), "tileClass": t.get("tileClass")}
                        for t in (b.get("tiles") or [])
                    ],
                }
                for b in bands
                if isinstance(b, dict)
            ],
            "sourceNote": str(d.get("sourceNote") or "")[:220],
        }
        ops = get_json(f"/api/apex/widgets/{page}?sub=ops", 60)
        if isinstance(ops, dict) and not ops.get("error"):
            ow = [w for w in (ops.get("widgets") or []) if isinstance(w, dict)]
            ob = ((ops.get("mosaicLayout") or {}).get("bands")) or []
            pages[page]["ops"] = {
                "n": len(ow),
                "ids": [w.get("id") for w in ow],
                "bands": [
                    {
                        "band": b.get("band"),
                        "tiles": [t.get("id") for t in (b.get("tiles") or [])],
                    }
                    for b in ob
                    if isinstance(b, dict)
                ],
            }
    live["pages"] = pages
    return json.dumps(live, indent=2, default=str)[:32000]


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No API key", file=sys.stderr)
        return 1
    # Staff machine: OPENROUTER_API_KEY holds a Moonshot sk-nv… key; native API + kimi-k2.5.
    if (api_key or "").startswith("sk-nv"):
        key_name = key_name or "MOONSHOT_API_KEY"
        base_url = "https://api.moonshot.ai/v1/chat/completions"
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    elif "moonshot.ai" in (base_url or "").lower():
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    else:
        model = str(
            os.getenv("MOONSHOT_MODEL")
            or os.getenv("KIMI_K2_MODEL")
            or "moonshotai/kimi-k2.5"
        ).strip()
    print(f"Using {key_name} @ {base_url} model={model}")

    excerpts = []
    for name, lim in (
        ("MOONSHOT_BEST_FILL_ZERO_SCROLL_CONSULT_2026-07-13.md", 3500),
        ("MOONSHOT_WIDGETS_SUCK_ZERO_SCROLL_CONSULT_2026-07-13.md", 2500),
    ):
        path = DOCS / name
        if path.is_file():
            excerpts.append(f"### {name}\n{path.read_text(encoding='utf-8', errors='replace')[:lim]}")

    live = live_snapshot()
    print("Live snapshot chars:", len(live))

    user = (
        f"OPERATOR REQUEST (verbatim):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        f"LIVE SNAPSHOT (hal-10617 leftovers):\n```json\n{live}\n```\n\n"
        + ("PRIOR CONSULT EXCERPTS:\n" + "\n\n".join(excerpts) if excerpts else "")
        + "\n\nReturn the markdown report only. CONSULT ONLY."
    )

    body = {
        "model": model,
        # kimi-k2.5 on api.moonshot.ai allows temperature=1 only
        "temperature": 1,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    url = base_url.rstrip("/")
    if not url.endswith("/chat/completions"):
        url = url + "/chat/completions"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=700) as resp:
            raw = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as exc:  # noqa: BLE001
        print(f"Moonshot call failed: {exc}", file=sys.stderr)
        return 2

    text = extract_message_content(raw) or ""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = OUT / f"moonshot_whats_left_after_fib_bands_{stamp}.json"
    md_path = DOCS / f"MOONSHOT_WHATS_LEFT_AFTER_FIB_BANDS_CONSULT_{DATE}.md"
    raw_path.write_text(json.dumps(raw, indent=2)[:500000], encoding="utf-8")

    header = (
        f"# Moonshot AI — What's left of the pages after Fibonacci bands (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Build:** hal-10617\n"
        f"**Script:** `scripts/run_moonshot_whats_left_after_fib_bands_consult.py`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    md_path.write_text(header + text.strip() + "\n", encoding="utf-8")
    print("Wrote", md_path)
    print("Raw", raw_path)
    print(text[:1200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
