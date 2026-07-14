"""Moonshot AI — Widgets look poor; can we swap ALL to compact zero-scroll? (CONSULT ONLY).

Operator: tell moonshot these widgets suck and like poor - without breaking
the program ask if all the widgets can be changed out and compacted so i do
not have to scroll down the page.
"""

from __future__ import annotations

import json
import os
import ssl
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

CTX = ssl._create_unverified_context()
BASE = os.getenv("NR2_BROWSER", "https://127.0.0.1:8765").rstrip("/")

OPERATOR_REQUEST_VERBATIM = (
    "tell moonshot these widgets suck and like poor - without breaking the "
    "program ask if all the widgets can be changed out and compacted so i do "
    "not have to scroll down the page"
)

SYSTEM = """You are Moonshot AI — principal engineer / product UI lead for NR2 Apex HAL
(BUILD currently **hal-10611**).

Operator says the widgets look poor / suck. Asks IF all widgets can be
CHANGED OUT and COMPACTED so they do NOT have to scroll down any page —
WITHOUT breaking the program.

CONSULT ONLY — DO NOT claim you applied code. empty ≠ $0. Never invent
SoftDent dollars. Prefer reuse of existing renderers in site/apex-core.js
over inventing 20 new chart engines.

HARD CONSTRAINTS:
- Zero-scroll target at 1920×1080 compact density (scrollHeight ≈ viewport)
- Height caps: micro ≤120, secondary ≤240, primary ≤320
- KPI budget ≤4 pills above fold (executive-strip)
- Empty collapses / omits — never pad $0
- SoftDent Output Options Excel or Print Preview only when OPS needed
- Do not break: HAL chat, import sync, claims kanban subpage, taxes planning subpage, authenticity of empty states
- Already shipped: compact remaps, tax-core-strip, financial empty omit (hal-10611), claims aging m, SoftDent strips

YOUR JOB:
1) Honest answer: CAN all widgets be swapped/compacted for zero-scroll without breaking the program? (yes/partial/no)
2) What MUST stay vs what CAN be replaced / demoted / moved to subpages/modals
3) Single coherent design package: a SHARED compact widget set for ALL pages
4) Per-page swap map (financial, softdent, claims, taxes, ar, qb, office-manager, documents, narratives, hal)
5) Correct coding if approved later (MUST/SHOULD — real paths, surgical)
6) Risk of breakage + rollback
7) Report for operator

OUTPUT (strict markdown):
# Verdict (one sentence: can we change them all out for zero-scroll without breaking?)
## 0. Operator Intent (verbatim; confirm consult-only)
## 1. Why the widgets feel poor (blunt diagnosis)
## 2. Can we change ALL out? (yes / partial / no — with reasons)
## 3. Zero-scroll compact contract (shared primitives for every page)
## 4. What MUST keep vs what to swap / demote / subpage
## 5. Per-page remaps (tall → compact)
## 6. Coding package if approved (MUST / SHOULD; real files only; diffs only if short)
## 7. Breakage risks + how to not break the program
## 8. What NOT to redo / invent
## 9. Acceptance criteria (scrollHeight gate)
## 10. Executive Summary (5 bullets)
## 11. Approval checklist
Be blunt. Prefer one ship package over a wish list.
"""


def get_json(path: str, timeout: int = 90):
    try:
        with urllib.request.urlopen(BASE + path, context=CTX, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        return {"error": type(e).__name__, "msg": str(e)[:200]}


def live() -> str:
    info = get_json("/api/app-info", 15)
    census = get_json("/api/apex/widget-census", 90)
    pages = {}
    for page in (
        "financial",
        "softdent",
        "claims",
        "taxes",
        "ar",
        "quickbooks",
        "office-manager",
        "documents",
        "narratives",
        "hal",
    ):
        d = get_json(f"/api/apex/widgets/{page}", 90)
        if not isinstance(d, dict) or d.get("error"):
            pages[page] = d
            continue
        widgets = [w for w in (d.get("widgets") or []) if isinstance(w, dict)]
        types: dict[str, int] = {}
        sizes: dict[str, int] = {}
        for w in widgets:
            t = str(w.get("type") or "?")
            s = str(w.get("size") or "?")
            types[t] = types.get(t, 0) + 1
            sizes[s] = sizes.get(s, 0) + 1
        pages[page] = {
            "buildId": d.get("buildId"),
            "warming": d.get("warming"),
            "n": len(widgets),
            "typesTop": dict(sorted(types.items(), key=lambda x: -x[1])[:10]),
            "sizes": sizes,
            "idsHead": [w.get("id") for w in widgets[:12]],
        }
    slim_census = []
    for p in (census.get("pages") or []) if isinstance(census, dict) else []:
        if isinstance(p, dict):
            slim_census.append(
                {
                    "page": p.get("page"),
                    "total": p.get("total"),
                    "withData": p.get("withData"),
                    "empty": p.get("empty"),
                }
            )
    snap = {
        "schema": info.get("schemaVersion") if isinstance(info, dict) else None,
        "asset": info.get("assetVersion") if isinstance(info, dict) else None,
        "census": slim_census,
        "pages": pages,
    }
    path = OUT / "moonshot_widgets_suck_live.json"
    path.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    return (
        "### Live snapshot\n```json\n"
        + json.dumps(snap, indent=2)[:12000]
        + "\n```\n\n"
        "### Already shipped (do not pretend missing)\n"
        "- hal-10610 compact remap (taxes strip, claims aging m, SoftDent strips)\n"
        "- hal-10611 build sync + financial empty omit (status==empty non-exempt)\n"
        "- apex_compact_pages_pack height tiers + KPI micro-strip + zero-scroll contract\n"
        "- Claims kanban already on #claims/kanban subpage\n"
        "- Taxes planning table/calendar on #taxes/planning\n"
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
        f"{live()}\n"
        "Answer bluntly: can we change ALL widgets out and compact for zero-scroll "
        "without breaking the program? Consult only — coding for later approval."
    )

    payload = {
        "model": model,
        "temperature": 1.0 if "moonshot" in base_url.lower() else 0.2,
        "max_tokens": 10000,
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
            "X-Title": "NR2 Moonshot Widgets Suck Zero-Scroll Consult",
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
    raw = OUT / f"moonshot_widgets_suck_raw_{stamp}.json"
    raw.write_text(
        json.dumps(
            {"model": model, "key": key_name, "operator": OPERATOR_REQUEST_VERBATIM, "content": content},
            indent=2,
        ),
        encoding="utf-8",
    )
    doc = DOCS / f"MOONSHOT_WIDGETS_SUCK_ZERO_SCROLL_CONSULT_{DATE}.md"
    header = (
        f"# Moonshot AI — Widgets suck / zero-scroll swap (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Build:** hal-10611\n"
        f"**Script:** `scripts/run_moonshot_widgets_suck_zero_scroll_consult.py`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    doc.write_text(header + content + "\n", encoding="utf-8")
    print(f"wrote {doc}", flush=True)
    print(f"wrote {raw}", flush=True)
    # ascii preview
    import re

    print("--- PREVIEW ---", flush=True)
    print(re.sub(r"[^\x00-\x7F]+", "?", content)[:5500], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
