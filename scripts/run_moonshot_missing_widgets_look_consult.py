"""Moonshot AI — Missing widgets that would be great + how they look (CONSULT ONLY).

Operator request is passed VERBATIM. Do not rewrite operator intent.
Does NOT apply any code.
"""

from __future__ import annotations

import json
import os
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

OPERATOR_REQUEST_VERBATIM = """
ask moonshot ai what widgets i dont have woul be great for the program and show wha they look like, report
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — product architect + Apex starship-bridge
UI designer for NewRidge Financial 2.0 (NR2), a local HTTPS Bottle browser app for a
Kansas dental S-corp (SoftDent + QuickBooks imports, local HAL).

CRITICAL CONSTRAINTS:
1. Answer the operator request VERBATIM: which widgets they DO NOT already have that
   would be GREAT for the program — AND SHOW WHAT THEY LOOK LIKE. Then REPORT.
2. CONSULT ONLY — DO NOT APPLY / DO NOT CODE into the live app.
3. Use LIVE FACTS + attached context as ground truth. NEVER invent dollar amounts,
   claim IDs, patients, ERA %, or clinical facts. Sample visuals must use null/empty
   or clearly labeled PLACEHOLDER labels (e.g. "Provider A", "$—", "No data").
4. Focus on MISSING instruments — do NOT recommend things already shipped (see LIVE
   FACTS inventory). If an idea overlaps an existing type, skip it or explain why a
   NEW variant is still worth building.
5. Prefer Apex-native mosaic instruments (vanilla JS/CSS/canvas/SVG). No third-party
   embeds (TradingView, bank OAuth, Plaid). No resurrected mockups.
6. For EACH recommended missing widget you MUST show appearance with:
   - Short visual description (layout, chrome, colors in cyan/amber/magenta starship palette)
   - ASCII / box-drawing wireframe mockup of the instrument face (what operator sees)
   - Optional tiny SVG sketch (inline markdown) if it clarifies the look
7. Rank MUST / SHOULD / NICE. Map each to page(s) + import-backed data source + honesty
   empty-state behavior. Effort XS/S/M/L.
8. Cap at ~8–12 best missing widgets (quality over laundry list). Prefer practice-ops
   value (production, collections, A/R, claims, taxes, import health, office manager).

OUTPUT FORMAT (strict markdown):
# Verdict
## 0. Operator Intent (quote; confirm consult-only)
## 1. Already Have (skip list — brief)
## 2. Missing Widgets That Would Be Great (ranked)
For each widget:
### W-NN — Name (MUST|SHOULD|NICE · Effort)
- Why great / page(s) / data source / honesty
- Look: 2–4 sentence visual description
- Wireframe: ASCII mockup
- Optional SVG sketch
## 3. Gallery Summary (one-line look per widget)
## 4. Implementation Phases (DO NOT APPLY until approve)
## 5. Risks & Rollback
"""


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 30),
    ("NewRidgeFinancial2/docs/MOONSHOT_BAR_TREND_PAGE_ORG_CONSULT_2026-07-11.md", 80),
    ("NewRidgeFinancial2/docs/MOONSHOT_MORE_WIDGETS_FLASH_CONSULT_2026-07-10.md", 60),
    ("NewRidgeFinancial2/docs/MOONSHOT_WIDGET_IDEAS_CONSULT_2026-07-10.md", 40),
    ("NewRidgeFinancial2/site/apex-core.js", 120),
    ("NewRidgeFinancial2/apex_backend.py", 80),
]


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} lines truncated]"


def build_context() -> str:
    parts: list[str] = []
    for rel, max_lines in CONTEXT_FILES:
        path = REPO / rel
        if not path.is_file():
            parts.append(f"### FILE: {rel}\n(missing)")
            continue
        body = _truncate(path.read_text(encoding="utf-8", errors="replace"), max_lines)
        ext = path.suffix.lstrip(".") or "txt"
        parts.append(f"### FILE: {rel}\n```{ext}\n{body}\n```")
    parts.append(
        """### LIVE FACTS (hal-10441+) — ALREADY SHIPPED INSTRUMENT TYPES (DO NOT RE-RECOMMEND AS NEW)
Core: kpi, status, chart/bar/line, pulse, remainder, funnel, countdown, heatmap,
calculator, categorize, hal-chat, narratives/tax-library
Charts: horizontal-bar, donut, stacked-bar, waterfall, bullet, dual-axis-trend,
revenue-composition, scrubber
Financial/CPA: ebitda-scrubber, ebitda-station, scenario-manager, filing-workflow,
workpaper, financial-command-strip, executive-strip
Claims: claim-shelf, claims-kanban/workbench, claims-header-stats, claims-executive-strip,
claims-aging-exposure, claims-critical-actions, claims-risk-bars, claims-era-gauge,
claim-attachments, daily-huddle
Chrome already: phosphor glow, holographic hover, corner brackets, scan sweep, nav LEDs,
stage glitch, grid floor, dual tickers, HAL neural core
Pages: financial, taxes, softdent, quickbooks, ar, claims, narratives, documents,
library, office-manager, hal
Hard rules: never invent dollars; honest empty states; Apex-native only; consult report only.
Operator asks: widgets they DON'T have that would be GREAT + SHOW WHAT THEY LOOK LIKE.
"""
    )
    return "\n\n".join(parts)


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No Moonshot/OpenRouter API key.", file=sys.stderr)
        return 1

    if "moonshot" in (base_url or "").lower():
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    else:
        model = str(
            os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2"
        ).strip()

    print(f"Using {key_name} @ {base_url} model={model}")
    user = (
        "OPERATOR REQUEST (VERBATIM — do not rewrite):\n\n"
        f"{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Recommend MISSING widgets that would be great for NR2-Apex. "
        "SHOW WHAT EACH LOOKS LIKE (ASCII wireframe + visual description). "
        "CONSULT ONLY — report; do not apply code.\n\n"
        "## Codebase context\n\n"
        + build_context()
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 14000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Missing Widgets Look Consult"

    print("Calling Moonshot AI (consult only — will not apply)...")
    req = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3600) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = extract_message_content(body)
        status = "ok"
    except urllib.error.HTTPError as exc:
        content = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:4000]}"
        status = f"HTTP {exc.code}"
    except Exception as exc:
        content = str(exc)
        status = "error"

    header = (
        f"# Moonshot AI — Missing Widgets + How They Look (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10441+  \n"
        f"**Script:** `scripts/run_moonshot_missing_widgets_look_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator validates.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_MISSING_WIDGETS_LOOK_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_MISSING_WIDGETS_LOOK_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
