"""Moonshot AI — More financial widgets (bar graphs etc.) + flashy pro items (CONSULT ONLY).

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
ask moonshot ai are there any more financial widgets like bar graphs that can be placed in the pages as well as any other flashy highly professional items then report dont code until i approve
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — product architect + starship-bridge UI designer
for NewRidge Financial 2.0 (NR2), a local HTTPS Bottle browser app for a dental practice.

CRITICAL CONSTRAINTS:
1. Answer BOTH parts of the operator request:
   (A) More financial widgets LIKE bar graphs that can be placed on Apex pages.
   (B) Any other flashy, highly professional presentation items (chrome / motion / instruments).
2. Do not rewrite the operator's request — treat their wording as source of truth.
3. CONSULT ONLY — DO NOT APPLY / DO NOT CODE into the live app until operator approves.
4. Current live build is NR2-Apex starship bridge **hal-10280**:
   - Shell: left sidebar, top TELEMETRY ticker, bottom OPS ticker, mosaic stage, grid floor
   - Flash chrome already: phosphor glow, holographic hover, corner brackets, scan sweep, nav LEDs, stage glitch, neural core on HAL
   - Instrument types already: kpi, status, chart (bar/line canvas), pulse, remainder, funnel, countdown, heatmap, calculator, categorize, hal-chat, narratives
   - Pages: financial, taxes, softdent, quickbooks, ar, claims, narratives, documents, library, office-manager, hal
5. Keep wipe-safe: do NOT resurrect moonshot-mockup / live-wire / third-party embeds (TradingView, Investing.com, bank OAuth).
6. Native Apex only: vanilla JS + CSS + canvas/SVG. Prefer extending existing ApexChartWidget / mosaic types.
7. NEVER invent financial dollar amounts. Sample payloads must use null/empty or clearly labeled PLACEHOLDER structure — values only from SoftDent/QB imports when describing data contracts.
8. Respect prefers-reduced-motion; avoid purple-glow cliché; stay cyan/amber/magenta scientific starship aesthetic.
9. Rank by impact vs risk (perf, distraction, a11y, honesty of empty states).
10. Map each widget idea to specific Apex page(s) and import-backed data source when possible.
11. Provide paste-ready SPEC / schema / optional foundation snippets in a "Code Deliverables" section labeled CONSULT ONLY — but the report must make clear nothing is applied.

OUTPUT FORMAT (strict markdown):
# Verdict
## 0. Operator Intent (quote; confirm consult-only / no code until approve)
## 1. More Financial Widgets (bar graphs and kin)
Table or ranked list: name | chart/widget type | page(s) | import data source | MUST/SHOULD/NICE | honesty notes
## 2. Other Flashy Highly Professional Items
Ranked chrome/motion/instrument ideas beyond charts; mark MUST/SHOULD/NICE; note what is already present at hal-10280 so you do not duplicate.
## 3. Per-Page Placement Map
One short block per Apex page with recommended additions (or "saturated — skip").
## 4. Moonshot Spec Deliverables (paste-ready, CONSULT ONLY)
Instrument JSON shapes + optional CSS/JS stubs. No invented dollars.
## 5. Implementation Phases (W0 validate → Wn) + Validation Gate
DO NOT APPLY until operator says proceed / validated / approve.
## 6. Risks & Rollback
"""


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 20),
    ("NewRidgeFinancial2/docs/MOONSHOT_REMAINING_UPDATES_APPLIED_2026-07-10.md", 50),
    ("NewRidgeFinancial2/docs/MOONSHOT_VISUAL_BOOST_APPLIED_2026-07-10.md", 40),
    ("NewRidgeFinancial2/docs/MOONSHOT_FLASHY_APPLIED_2026-07-10.md", 40),
    ("NewRidgeFinancial2/site/apex-core.js", 80),
    ("NewRidgeFinancial2/apex_backend.py", 100),
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
        """### LIVE FACTS (hal-10280)
- Already have bar/line charts via ApexChartWidget on several pages (financial, QB, SoftDent, A/R, claims).
- Visual boosts already: morning-brief, liquidity-pulse, collectible-remainder, ar-heatmap, claims funnel, tax countdown, patient-responsibility calculator, categorize assist.
- Flash already: phosphor, holographic lift, brackets, scan sweep, nav LEDs, stage glitch, grid floor, dual tickers, HAL neural core.
- Operator asks: MORE financial widgets like bar graphs + OTHER flashy highly professional items; REPORT ONLY; do not code until approve.
- Hard rule: never invent dollar amounts; honest empty states; no third-party embeds.
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
        "CONSULT ONLY — report ideas. Do not apply code. Wait for operator approve.\n\n"
        "## Context\n\n"
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
        headers["X-Title"] = "NR2 More Widgets Flash Consult"

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
        f"# Moonshot AI — More Financial Widgets + Flashy Pro Items (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10280  \n"
        f"**Script:** `scripts/run_moonshot_more_widgets_flash_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_MORE_WIDGETS_FLASH_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_MORE_WIDGETS_FLASH_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
