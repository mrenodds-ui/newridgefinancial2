"""Moonshot AI — all-pages extremely high-tech redesign + widget relocate/modify consult.

CONSULT ONLY. Writes report + paste-ready code. Does NOT apply changes.
Operator must validate before any merge.
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
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

sys.path.insert(0, str(OUT))
from _run_moonshot_eval import extract_message_content, resolve_api_and_endpoint  # noqa: E402

SYSTEM = """You are Moonshot AI (kimi-k2 class) — principal product designer + front-end architect
for NewRidge Financial 2.0 (dental practice financial OS on loopback).

OPERATOR REQUEST (CRITICAL — answer fully):
1. Design an EXTREMELY high-tech look for ALL live staff pages, using the CURRENT widgets.
2. Provide paste-ready CODE to implement that look.
3. Explicitly answer: CAN some widgets be ALTERED / MODIFIED and PLACED in OTHER PARTS of the pages?
   - If YES: which widgets, how to alter (type/colSpan/chrome only vs binder changes), where to move them,
     and exact layout JSON / engine patches.
   - If NO for a widget: say why (data honesty, binder coupling, single-page ownership).
4. REPORT BEFORE CODING is already satisfied by this consult — do NOT assume anything is merged.
   Status must remain REVIEW ONLY.

CURRENT STATE (2026-07-09, build hal-10168):
- staffRenderMode: live-wire-pilot — MoonshotLayoutEngine owns all 11 staff pages (no mock-embed iframe).
- Mission-control Terminal Glass CSS already partially applied (nr2-mission-control-glass.css).
- Page headers + filter chips (30d/90d/YTD/All) already injected by layout engine.
- Layout inventory: moonshot-page-layouts.js (panel order, colSpan, type, widgetKey).
- Honesty rules: empty widgets use widgetImportCta / canvasEmptyFor — NEVER fabricate $.
- Existing PageCanvas helpers only: heroKpiRow, canvasPanel, chartContainer, vBarChart, dualLineChart,
  conicDonut, canvasTable, canvasKanbanLanes, canvasStatGrid, canvasGauge, canvasFunnel, canvasHeatmap.

DESIGN TARGET (extreme high-tech):
- Bloomberg terminal × SpaceX mission control × institutional finance OS.
- Near-black obsidian, glass panels, monospace tabular figures, cyan/gold/severity signal language,
  denser grid, intentional motion (2–4 CSS animations max), severity heat on A/R/claims.
- Keep brand/sidebar; do not invent new widget keys or new data pipelines.
- Prefer: (A) CSS + class chrome, (B) reorder/resize panels in moonshot-page-layouts.js,
  (C) change panel `type` only when the same dataBind already supports that renderer,
  (D) small layout-engine shell tweaks. Avoid rewriting binders unless required for relocate.

HARD RULES:
1. Existing widget keys / dataBinds only — do not invent new keys.
2. Relocating a widget = move/reorder panel object (and optionally change colSpan/type) in layouts.
3. Altering a widget = chrome/CSS, density, accent, or safe type swap (e.g. table→stat-grid) ONLY if
   the existing dataBind shape already works with that renderer — call out risk if not.
4. Preserve live-wire honesty empty states.
5. Paste-ready code with exact paths under NewRidgeFinancial2/site/ (and deferred-live-wire mirrors).
6. Mark every change P0/P1/P2 with acceptance criteria.
7. No emoji in production widget titles.
8. Dual-mirror note: if you patch moonshot-layout-engine.js or moonshot-page-layouts.js, patch BOTH
   NewRidgeFinancial2/site/deferred-live-wire/ AND NewRidgeFinancial2/deferred-live-wire/.

OUTPUT FORMAT (strict markdown):
# Verdict
One paragraph: will this read as extremely high-tech in <5 seconds? Yes/No + why.
## 1. Widget alter / relocate policy (ANSWER THE OPERATOR DIRECTLY)
### 1a. What MAY be altered
Table: WidgetKey | Current page | Allowed alter (chrome / type / density) | Risk
### 1b. What MAY be relocated (to other parts of SAME page or CROSS-page)
Table: WidgetKey | From | To (page + position) | Why high-tech | Layout change summary
### 1c. What must NOT move or invent
Short list + reasons.
### 1d. Recommended composition rules
Hero band / primary instrument / secondary strip / footer utility — how to place widgets.
## 2. Visual Design System (extreme)
Tokens, typography, glass, glow, motion budget, severity language — beyond what glass CSS already has.
## 3. Page-by-page redesign (ALL 11)
For EACH of: financial, softdent, quickbooks, ar, taxes, claims, narratives, documents, library,
office-manager, hal:
- Current weak composition
- Target composition (wireframe in words: row1 / row2 / …)
- Widgets to KEEP / MOVE / RESIZE / TYPE-SWAP / DE-EMPHASIZE
- Accent / density notes
## 4. Moonshot Code Deliverables
### File: <exact path>
```css or javascript
paste-ready full patches or clearly delimited search/replace blocks
```
Minimum:
- nr2-mission-control-glass.css (or new companion CSS) — extreme density + instruments
- moonshot-page-layouts.js — reordered/resized/type-swapped panels (BOTH mirrors if changed)
- moonshot-layout-engine.js — only if shell/chrome needed (BOTH mirrors)
- Optional page-canvas.js class hooks — no binder honesty changes
## 5. Diff vs current hal-10168 live pages
What operator will notice that Terminal Glass alone did not deliver (layout moves matter).
## 6. Operator Validation Gate
Browser checklist per page (headers, no iframe, relocated widgets visible, empty CTAs honest).
## 7. Prioritized apply order (max 5 commits) — WAIT for operator "proceed"
Do not apply. Consult only.
"""


def read_file(rel: str, max_chars: int = 12000) -> str:
    path = REPO / rel
    if not path.is_file():
        return f"(missing {rel})"
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + f"\n...[{len(text) - max_chars} chars truncated]..."
    return text


def read_truncated(rel: str, max_lines: int = 200) -> str:
    path = REPO / rel
    if not path.is_file():
        return f"(missing {rel})"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    body = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        body += f"\n... [{len(lines) - max_lines} lines truncated] ..."
    return f"### {rel}\n```\n{body}\n```\n"


def elite_snip(page_id: str, max_chars: int = 2200) -> str:
    path = OUT / "page_mockups_elite" / f"{page_id}.html"
    if not path.is_file():
        return f"(missing elite {page_id}.html)"
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[:max_chars] + ("\n...[truncated]..." if len(text) > max_chars else "")


def build_user() -> str:
    parts: list[str] = [
        "# Operator brief",
        "Extremely high-tech redesign for ALL pages using CURRENT widgets.",
        "Ask/answer: can widgets be altered/modified and placed in other parts of pages?",
        "Return full report + paste-ready code. DO NOT APPLY.",
        "",
        "# Current build",
        f"### nr2-build.json\n```json\n{read_file('NewRidgeFinancial2/nr2-build.json')}\n```\n",
        "# Full live layout inventory (authoritative widget placement today)",
        f"### moonshot-page-layouts.js\n```javascript\n"
        f"{read_file('NewRidgeFinancial2/site/deferred-live-wire/moonshot-page-layouts.js', 28000)}\n```\n",
        "# Layout engine render chrome (headers already present)",
        read_truncated(
            "NewRidgeFinancial2/site/deferred-live-wire/moonshot-layout-engine.js",
            220,
        ),
        "# Mission-control glass already shipped (extend, do not discard)",
        f"### nr2-mission-control-glass.css\n```css\n"
        f"{read_file('NewRidgeFinancial2/site/nr2-mission-control-glass.css', 10000)}\n```\n",
        "# Vocabulary / glow (cascade context)",
        read_truncated("NewRidgeFinancial2/site/nr2-mockup-page-vocabulary.css", 80),
        read_truncated("NewRidgeFinancial2/site/nr2-moonshot-glow.css", 60),
        "# Prior high-tech consult (CSS-only; operator now wants relocate/alter too)",
        f"### Prior consult excerpt\n```markdown\n"
        f"{read_file('NewRidgeFinancial2/docs/MOONSHOT_HIGHTECH_VISUAL_CONSULT_2026-07-09.md', 6000)}\n```\n",
        "# Elite visual language samples (structure inspiration — live-wire, not iframe)",
    ]
    for pid in ("financial", "claims", "quickbooks", "softdent", "ar", "narratives"):
        parts.append(f"## Elite {pid}.html\n```html\n{elite_snip(pid)}\n```\n")
    parts.append(
        "Respond with the strict OUTPUT FORMAT. Be decisive on widget relocate/alter. "
        "Extreme high-tech must be obvious in under 5 seconds. Include paste-ready code."
    )
    return "\n".join(parts)


def call_moonshot(system: str, user: str) -> tuple[str, str, str]:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        raise RuntimeError("No Moonshot/OpenRouter API key available")

    candidates: list[tuple[str, str]] = []
    if "openrouter" in (base_url or "").lower() or "OPENROUTER" in (key_name or "").upper():
        candidates.append((base_url, "moonshotai/kimi-k2.5"))
        candidates.append((base_url, "moonshotai/kimi-k2"))
        candidates.append(("https://api.moonshot.ai/v1/chat/completions", "kimi-k2.5"))
    else:
        candidates.append((base_url or "https://api.moonshot.ai/v1/chat/completions", "kimi-k2.5"))
        candidates.append(("https://api.moonshot.ai/v1/chat/completions", "kimi-k2.6"))
        candidates.append(("https://openrouter.ai/api/v1/chat/completions", "moonshotai/kimi-k2.5"))

    last_err = ""
    for url, mdl in candidates:
        payload = {
            "model": mdl,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 1,
        }
        if "api.moonshot." in url:
            payload["top_p"] = 0.95
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        if "openrouter.ai" in url:
            headers["HTTP-Referer"] = (
                os.getenv("OPENROUTER_HTTP_REFERER") or "https://github.com/NewRidgeFamilyFinancial"
            )
            headers["X-Title"] = (
                os.getenv("OPENROUTER_X_TITLE") or "NR2 All-Pages Hightech Relayout Consult"
            )
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=420) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = extract_message_content(data)
            if content and len(content.strip()) > 400:
                return content, mdl, key_name or "API_KEY"
            last_err = f"empty/short response from {mdl} @ {url}"
        except urllib.error.HTTPError as e:
            err_body = e.read()[:500]
            last_err = f"HTTP {e.code} {mdl} @ {url}: {err_body!r}"
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__} {mdl} @ {url}: {e}"
    raise RuntimeError(last_err or "Moonshot call failed")


def main() -> int:
    print("Building Moonshot all-pages high-tech + widget relayout consult…")
    user = build_user()
    prompt_path = OUT / f"ALL_PAGES_HIGHTECH_RELAYOUT_PROMPT_{DATE}.md"
    prompt_path.write_text(user, encoding="utf-8")
    print(f"Prompt saved: {prompt_path} ({len(user)} chars)")

    try:
        content, model, key_name = call_moonshot(SYSTEM, user)
    except Exception as e:  # noqa: BLE001
        err = f"# Moonshot All-Pages High-Tech Relayout Consult FAILED\n\n{e}\n"
        fail_path = DOCS / f"MOONSHOT_ALL_PAGES_HIGHTECH_RELAYOUT_CONSULT_{DATE}_FAILED.md"
        fail_path.write_text(err, encoding="utf-8")
        print(err, file=sys.stderr)
        return 1

    header = (
        f"# Moonshot AI — All-Pages Extremely High-Tech Redesign + Widget Relayout\n"
        f"**Date:** {DATE}\n"
        f"**Model:** {model} via {key_name}\n"
        f"**Status:** REVIEW ONLY — do not apply until operator validates\n"
        f"**Script:** `scripts/run_moonshot_all_pages_hightech_relayout_consult.py`\n"
        f"**Scope:** All 11 live-wire pages; current widgets; alter/relocate allowed if safe; "
        f"paste-ready code included; NO code applied\n\n"
        f"---\n\n"
    )
    report = header + content.strip() + "\n"
    out_docs = DOCS / f"MOONSHOT_ALL_PAGES_HIGHTECH_RELAYOUT_CONSULT_{DATE}.md"
    out_log = OUT / f"MOONSHOT_ALL_PAGES_HIGHTECH_RELAYOUT_CONSULT_{DATE}.md"
    out_docs.write_text(report, encoding="utf-8")
    out_log.write_text(report, encoding="utf-8")
    print(f"Wrote {out_docs}")
    print(f"Wrote {out_log}")
    print(f"Chars: {len(report)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
