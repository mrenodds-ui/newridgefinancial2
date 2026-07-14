"""Moonshot AI — What's next after HAL-10618 leftover package (CONSULT ONLY).

Operator: next
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

OPERATOR_REQUEST_VERBATIM = "next"

SYSTEM = """You are Moonshot AI — principal UI/data architect + SoftDent RCM engineer
for NR2 Apex HAL (BUILD **hal-10618** just shipped on fix/main-validate-ci).

Operator said: next
CONSULT ONLY — do not claim applied. empty ≠ $0. Never invent SoftDent dollars.
Desktop SoftDent Excel/Print Preview remains period-close truth when needed.

JUST SHIPPED (commit 153ff1c, BUILD_ID=hal-10618):
Full leftover-pages package from prior consult:
1) OPS Debris Cleanup — claims double-micro gone (pipeline→ops); AR collection-bullet→ops;
   max one micro band; Ops pair-pad; no unknown-subpage on content/docs/narr/library ops
2) Stale freshness — nr2-data-freshness forceShow on Financial/SoftDent; stale-import-alert
   only when alerting
3) Re-linked apex-theme.css + apex-mobile-polish.css
4) Content Hub — sidebar Content merges Documents/Narratives/Library; legacy hashes redirect

PRIOR STACK: hal-10617 Fibonacci bands; hal-10616 five-tile zero-scroll; SoftDent money-first;
omit chronic empty SoftDent-source widgets; desktop Excel/Print Preview OPS playbook.

LIVE SNAPSHOT attached — treat as truth for residuals.

YOUR JOB — pick THE single best NEXT package (not a laundry list):
Prefer highest ROI that unblocks practice truth or removes real staff friction.
Prefer OPS when the blocker is a real SoftDent/QB pull (Register/Daysheet/ERA/Gold CSV)
rather than more layout surgery if the UI is already staff-ready.

OPEN CANDIDATES (pick ONE primary; name it):
A) OPS SoftDent period refresh (Register/Daysheet/AR Excel→C:\\SoftDentReportExports→Sync)
B) OPS Gold CSV / ERA first drop for settlement truth
C) CODE SoftDent Report Manager rights / multi-pull reliability
D) CODE Content Hub polish (interactive narratives mount edge cases, empty tiles)
E) CODE zero-scroll acceptance smoke (scrollHeight gate) across all pages
F) CODE HAL/import honesty for stale chips with ageMinutes (not dollars)
G) CODE merge PR / main tip coherence only if you're sure UI is done
H) Something better you see in the live snapshot (name it)

OUTPUT (strict markdown):
# Verdict (one sentence — THE next package)
## 0. Operator Intent (verbatim)
## 1. Confirmation of HAL-10618 apply (pass/fail; residual risks)
## 2. Recommended NEXT (name, why now, effort, REAL files or OPS steps, validation gate)
## 3. Why this beats other candidates now
## 4. Runner-ups (2–3)
## 5. What NOT to redo
## 6. Acceptance criteria
## 7. Executive Summary (5 bullets)
## 8. Approval checklist
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
        "buildExpected": "hal-10618",
        "operatorAsk": OPERATOR_REQUEST_VERBATIM,
        "lastCommitHint": "153ff1c HAL-10618",
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
            ][:24]
        }

    pages = {}
    for page in (
        "financial",
        "softdent",
        "claims",
        "ar",
        "content",
        "hal",
        "quickbooks",
        "taxes",
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
            "bands": [
                {
                    "band": b.get("band"),
                    "tiles": [t.get("id") for t in (b.get("tiles") or [])],
                }
                for b in bands
                if isinstance(b, dict)
            ],
            "sourceNote": str(d.get("sourceNote") or "")[:200],
        }
        ops = get_json(f"/api/apex/widgets/{page}?sub=ops", 60)
        if isinstance(ops, dict) and not ops.get("error"):
            ow = [w for w in (ops.get("widgets") or []) if isinstance(w, dict)]
            pages[page]["opsIds"] = [w.get("id") for w in ow]
    live["pages"] = pages

    # SoftDent honesty gaps if available
    for path, key in (
        ("/api/apex/hal/sync-status", "syncStatus"),
        ("/api/apex/gold-era-settlement/status", "goldEra"),
    ):
        live[key] = get_json(path, 45)

    return json.dumps(live, indent=2, default=str)[:32000]


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No API key", file=sys.stderr)
        return 1
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
        ("MOONSHOT_WHATS_LEFT_AFTER_FIB_BANDS_CONSULT_2026-07-14.md", 3500),
        ("MOONSHOT_BEST_FILL_ZERO_SCROLL_CONSULT_2026-07-13.md", 2000),
    ):
        path = DOCS / name
        if path.is_file():
            excerpts.append(f"### {name}\n{path.read_text(encoding='utf-8', errors='replace')[:lim]}")

    live = live_snapshot()
    print("Live snapshot chars:", len(live))

    user = (
        f"OPERATOR REQUEST (verbatim):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        f"LIVE SNAPSHOT after HAL-10618:\n```json\n{live}\n```\n\n"
        + ("PRIOR CONSULT EXCERPTS:\n" + "\n\n".join(excerpts) if excerpts else "")
        + "\n\nReturn the markdown report only. CONSULT ONLY."
    )

    body = {
        "model": model,
        "temperature": 1,  # kimi-k2.5 on moonshot.ai
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
    raw_path = OUT / f"moonshot_whats_next_after_hal10618_{stamp}.json"
    md_path = DOCS / f"MOONSHOT_WHATS_NEXT_AFTER_HAL10618_{DATE}.md"
    raw_path.write_text(json.dumps(raw, indent=2)[:500000], encoding="utf-8")

    header = (
        f"# Moonshot AI — What's next after HAL-10618 (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{model}`\n"
        f"**Key:** {key_name}\n"
        f"**Build:** hal-10618\n"
        f"**Script:** `scripts/run_moonshot_whats_next_after_hal10618_consult.py`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    md_path.write_text(header + text.strip() + "\n", encoding="utf-8")
    print("Wrote", md_path)
    print("Raw", raw_path)
    print(text[:1400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
