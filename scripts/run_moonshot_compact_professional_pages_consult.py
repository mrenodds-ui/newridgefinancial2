"""Moonshot AI — Compact professional Apex pages (CONSULT ONLY).

Operator request is passed VERBATIM. Do not rewrite operator intent.
Does NOT apply any code. Await operator approval before coding.
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
as an expert software enginer ask moonshot ai all pages are unorganized, huge widgets that wobble, how wold he compact the pages so that we shouldn't have to scroll  down and make all the pages look compact, highly profressional
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — principal UX/systems engineer + product
architect for NewRidge Financial 2.0 (NR2): local HTTPS Apex “starship bridge” for a
Kansas dental S-corp. SoftDent + QuickBooks imports, Bottle TLS on 127.0.0.1:8765,
Apex JS shell, local HAL (Ollama 24B).

You are answering an EXPERT SOFTWARE ENGINEER peer request about PAGE DENSITY /
PROFESSIONAL COMPACTION. Be blunt, precise, design-system concrete. No fluff.
No invented dollars / patients / claim IDs.

CRITICAL CONSTRAINTS:
1. Answer the operator request VERBATIM: pages feel unorganized; huge wobbling widgets;
   how to compact so operators need little/no vertical scroll; highly professional look
   across ALL Apex pages.
2. CONSULT ONLY — DO NOT APPLY / DO NOT CODE until operator explicitly approves.
3. Use LIVE FACTS + attached context as ground truth.
4. Prefer additive Apex CSS/layout + widget-size discipline over resurrecting retired
   mockups / legacy desktop.
5. Do not sacrifice honesty: empty ≠ $0; pending imports collapse to chips/strips,
   never leave huge empty monuments.
6. Call out already-shipped density work (Financial strip console, empty-collapse,
   bar/trend org) so we do not re-litigate — extend the pattern to ALL pages.
7. Address the literal “wobble”: CSS motions (apexBreathe, hover translate/scale,
   enter stagger, alert pulse, chrome sweep/glitch) that make large instruments feel
   unstable. Distinguish intentional presence motion vs motion noise.
8. Target: first viewport = curated command surface (KPI strip + 1 primary chart +
   action row). Secondary detail behind tabs/collapsible strips or subpages — not a
   vertical warehouse of XL cards.
9. Phased remediation with validation gates. State clearly: code only after approve.

OUTPUT FORMAT (strict markdown):
# Verdict (1–3 sentences, engineer-to-engineer)
## 0. Operator Intent (quote; confirm consult-only)
## 1. Diagnosis — Why Pages Feel Huge / Unorganized / Wobbly
Evidence from tokens, grid, instrument sizes, animations, page packs.
## 2. Compact Professional Design System (target density rules)
Concrete rules: widget sizes (xs/s/m/l/xl/full), grid columns, max first-viewport
instrument count, empty-state collapse, chart heights, typography scale, motion budget.
## 3. Page-by-Page Compaction Map
Table: Page | Current problem | Target first-viewport | Move/collapse | Effort
Cover: financial, taxes, softdent, quickbooks, ar, claims, narratives, documents,
library, office-manager, HAL.
## 4. Kill the Wobble — Motion Remediation
What to disable / soften / gate behind prefers-reduced-motion; what to keep.
## 5. Recommendations — MUST / SHOULD / NICE
Table: ID | Rank | Recommendation | Why | Effort | Depends on
## 6. Suggested Fix Order (phases) + Validation Gates
## 7. Risks, honesty, Rollback
DO NOT APPLY until operator says proceed / approve.
"""

CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 30),
    ("NewRidgeFinancial2/site/apex-tokens.css", 120),
    ("NewRidgeFinancial2/site/apex-chrome-flash.css", 80),
    ("NewRidgeFinancial2/site/apex-bridge.css", 80),
    ("NewRidgeFinancial2/docs/MOONSHOT_BAR_TREND_PAGE_ORG_CONSULT_2026-07-11.md", 80),
    ("NewRidgeFinancial2/docs/MOONSHOT_BAR_TREND_PAGE_ORG_APPLIED_2026-07-11.md", 40),
    ("NewRidgeFinancial2/docs/MOONSHOT_FINANCIAL_PRO_PRESENTATION_CONSULT_2026-07-10.md", 80),
    ("NewRidgeFinancial2/docs/MOONSHOT_SUBPAGES_EXPAND_APPLIED_2026-07-11.md", 40),
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

    # Focused CSS extracts for wobble + size
    tokens = REPO / "NewRidgeFinancial2" / "site" / "apex-tokens.css"
    if tokens.is_file():
        text = tokens.read_text(encoding="utf-8", errors="replace")
        for marker, label, n in (
            ("--apex-widget-min", "density tokens", 40),
            (".apex-inst--", "instrument size classes", 80),
            ("@keyframes apexBreathe", "apexBreathe wobble", 25),
            ("@keyframes apexEnter", "apexEnter stagger", 25),
            ("apex-alert-pulse", "alert pulse", 20),
        ):
            i = text.find(marker)
            chunk = text[i : i + 2200] if i >= 0 else f"(marker not found: {marker})"
            parts.append(f"### EXTRACT: apex-tokens.css — {label}\n```css\n{_truncate(chunk, n)}\n```")

    chrome = REPO / "NewRidgeFinancial2" / "site" / "apex-chrome-flash.css"
    if chrome.is_file():
        text = chrome.read_text(encoding="utf-8", errors="replace")
        for marker, label, n in (
            ("holographic instrument lift", "hover lift/scale", 30),
            ("@keyframes apexGlitch", "glitch", 25),
            ("@keyframes apexSweep", "background sweep", 20),
        ):
            i = text.lower().find(marker.lower()) if "holographic" in marker else text.find(marker)
            if "holographic" in marker:
                i = text.find("/* Holographic")
            chunk = text[i : i + 1800] if i >= 0 else f"(marker not found: {marker})"
            parts.append(f"### EXTRACT: apex-chrome-flash.css — {label}\n```css\n{_truncate(chunk, n)}\n```")

    parts.append(
        """### LIVE FACTS (operator session 2026-07-11 ~17:24 CT — ground truth)
- App: https://127.0.0.1:8765/ Apex Bridge, schema/build **hal-10502**, staffRenderMode=apex.
- Import readiness recently fixed to **fresh** (critical-only completeness); warning/optional
  gaps no longer 403 money reads. Widgets can load again — density/wobble is now the UX complaint.
- Operator (expert SE voice): ALL pages feel unorganized; widgets are HUGE and WOBBLE;
  wants compaction so little/no scroll-down; highly professional look.
- Prior density work already shipped (do not redo, extend):
  - Financial Executive Console strip architecture + empty collapse (pro presentation).
  - Bar/trend page org pack (hal-10450) — more charts + empty→strip.
  - Subpages expand; HAL chat rail narrowed earlier; widget auto-refresh 30m (less flicker).
- Still visible motion that can read as “wobble” on large instruments:
  - `apexBreathe` infinite ease-in-out on some widgets
  - hover `translateY(-2px)` / chrome `translateY(-3px) scale(1.015)`
  - enter animation `translateY(10px)` + staggered delays
  - alert pulse / LED pulse / occasional glitch / background sweep
- Grid: `auto-fit` minmax(--apex-widget-min: 140px); many instruments sized l/xl/full with
  min-heights 100–180px+ and span-2; full-bleed shelves push first viewport past fold.
- Hard rules: PHI local; never invent $; empty stays honest (collapse, don’t fake KPIs);
  consult-only until operator approves coding.
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
        "You are being consulted by an expert software engineer. Diagnose why Apex pages "
        "feel huge, unorganized, and wobbly. Prescribe a compact, highly professional "
        "density system + page-by-page compaction + motion remediation + phased coding "
        "plan. CONSULT ONLY — do not apply code.\n\n"
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
        headers["X-Title"] = "NR2 Compact Professional Pages Consult"

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
        f"# Moonshot AI — Compact Professional Pages (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10502  \n"
        f"**Script:** `scripts/run_moonshot_compact_professional_pages_consult.py`  \n"
        f"**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_COMPACT_PROFESSIONAL_PAGES_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_COMPACT_PROFESSIONAL_PAGES_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
