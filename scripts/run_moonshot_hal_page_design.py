"""Ask Moonshot AI (kimi) to design all NR2 pages — layout manifest + HAL-ready render code."""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / ".local_logs" / "moonshot_financial_eval"
OUT.mkdir(parents=True, exist_ok=True)
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# Reuse key resolution from eval harness
sys.path.insert(0, str(OUT))
from _run_moonshot_eval import extract_message_content, resolve_api_and_endpoint  # noqa: E402

SYSTEM = """You are Moonshot AI — lead product designer + front-end architect for NewRidge Financial 2.0.

The operator wants YOU to invent the entire staff + HAL page layouts: professional high-tech financial widgets,
charts, kanban, tables — your own creative structure (not a copy of old mockups). Every panel MUST work with HAL.

HARD RULES (production, not HTML mockups):
1. Output a **layout manifest JSON** per page batch + **JavaScript** that plugs into existing PageCanvas helpers.
2. Every primary widget panel needs exactly one `data-hal-widget-key` from PageSchema (no duplicates per page).
3. Secondary panels use `data-hal-subpanel="name"` instead of duplicating widget keys.
4. Use existing helper functions only — do NOT invent new chart libraries:
   stackOpen(), dashboardPageOpen(), heroKpiRow(), canvasPanel(), canvasGrid12(), gridCol(),
   chartContainer(), vBarChart(), dualLineChart(), conicDonut(), canvasTable(), canvasKanbanLanes(),
   canvasStatGrid(), canvasGauge(), canvasFunnel(), canvasHeatmap(), canvasEmpty(), dashboardHost().
5. Bind data via PageCanvasData methods (e.g. D.financialKpis(), D.productionTrendSeries()) — list bind method per panel.
6. Layout shells: staff pages use `widget-grid` (stackOpen) OR `dashboard-grid` (dashboardPageOpen for QB/office-manager).
7. validate-pages.mjs requires unique data-hal-widget-key per page and all PageSchema.widgets keys present.
8. Dark moonshot theme classes already in CSS — use widget-card, kpi-large, chart-container, dashboard-grid, stats-bar, kanban-board.

OUTPUT FORMAT (strict):
### File: moonshot_layouts/<batch-id>.json
```json
{ "pages": { "<pageId>": { "title": "...", "shell": "widget-grid|dashboard-grid", "panels": [...] } } }
```
Each panel object: { "id", "type": "hero-kpi|chart|table|kanban|gauge|donut|funnel|heatmap|stat-grid|custom",
  "widgetKey"|"halSubpanel", "colSpan", "title", "dataBind": "PageCanvasData.method()", "chartType"?: "bar|line|dual|donut" }

### File: moonshot_layouts/<batch-id>_renderers.js
```javascript
// render functions using PageCanvas closure helpers — one function per page in batch
function renderFinancialMoonshot() { ... return stackOpen() + ... + '</div>'; }
```

### Summary
5-line operator summary of design choices.

Be creative on information hierarchy and chart selection. Prioritize operator questions each page answers."""

BATCHES: list[tuple[str, list[str], str]] = [
    (
        "overview",
        ["financial", "taxes", "hal"],
        "Overview: executive financial cockpit, S-corp tax planning, HAL command mosaic with Ask HAL + widget tiles.",
    ),
    (
        "clinical",
        ["softdent", "narratives", "claims"],
        "Clinical: practice performance, narrative composer, claims workbench with analytics + pipeline.",
    ),
    (
        "revenue",
        ["ar", "quickbooks"],
        "Revenue: A/R collections heatmap/waterfall, QuickBooks dashboard-grid P&L and EBITDA.",
    ),
    (
        "operations",
        ["documents", "library", "office-manager"],
        "Operations: accounting docs, library search, office manager stats-bar + dashboard-grid.",
    ),
]


def read_truncated(rel: str, max_lines: int = 180) -> str:
    path = REPO / rel
    if not path.is_file():
        return f"(missing {rel})"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    body = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        body += f"\n... [{len(lines) - max_lines} lines truncated]"
    return body


def build_user(batch_id: str, page_ids: list[str], focus: str) -> str:
    schema = read_truncated("NewRidgeFinancial2/site/moonshot-page-registry.js", 320)
    canvas = read_truncated("NewRidgeFinancial2/site/page-canvas.js", 280)
    data = read_truncated("NewRidgeFinancial2/site/page-canvas-data.js", 200)
    hal_canvas = read_truncated("NewRidgeFinancial2/site/hal-page-canvas.js", 120)
    contract = read_truncated("NewRidgeFinancial2/site/widget-contract.js", 100)

    page_specs = []
    for pid in page_ids:
        page_specs.append(f"- **{pid}**: include ALL widgets from PageSchema.byId('{pid}').widgets")

    return f"""Design Moonshot-original layouts for batch `{batch_id}`.

## Operator intent
Moonshot must invent the full page UX (widgets, charts, hierarchy) for these pages: {", ".join(page_ids)}.
{focus}

## Pages in this batch
{chr(10).join(page_specs)}

## PageSchema (excerpt)
```javascript
{schema}
```

## PageCanvas helpers (excerpt)
```javascript
{canvas}
```

## PageCanvasData binders (excerpt)
```javascript
{data}
```

## HAL page canvas (excerpt)
```javascript
{hal_canvas}
```

## Widget contract (excerpt)
```javascript
{contract}
```

Deliver JSON manifest + renderer JS for: {", ".join(page_ids)}.
HAL must scroll to any `data-hal-widget-key`, cite metrics via halWidgetFeed, and open pages from HAL mosaic tiles."""


def call_model(api_key: str, base_url: str, user: str) -> tuple[str, str]:
    payload = {
        "model": "kimi-k2.5",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 16384,
    }
    req = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            body = json.loads(resp.read().decode())
        return extract_message_content(body), "ok"
    except urllib.error.HTTPError as exc:
        return f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:4000]}", f"HTTP {exc.code}"
    except Exception as exc:
        return str(exc), "error"


def extract_files(markdown: str, dest: Path) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    pattern = re.compile(
        r"### File:\s*moonshot_layouts/([^\s]+)\s*\n```(?:json|javascript|js)?\s*\n([\s\S]*?)```",
        re.MULTILINE,
    )
    for match in pattern.finditer(markdown):
        name, content = match.group(1), match.group(2).strip()
        path = dest / name
        path.write_text(content + "\n", encoding="utf-8")
        written.append(name)
    return written


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No working Moonshot/OpenRouter API key found.")
        return 1
    print(f"Using {key_name} @ {base_url}")

    layout_dir = OUT / "moonshot_layouts"
    layout_dir.mkdir(parents=True, exist_ok=True)
    combined: list[str] = []
    all_written: list[str] = []

    for batch_id, page_ids, focus in BATCHES:
        print(f"\n--- Batch {batch_id}: {', '.join(page_ids)} ---")
        user = build_user(batch_id, page_ids, focus)
        text, status = call_model(api_key, base_url, user)
        out_md = OUT / f"MOONSHOT_HAL_PAGE_DESIGN_{batch_id}_{DATE}.md"
        out_md.write_text(f"# Moonshot HAL page design — {batch_id}\n\nStatus: {status}\n\n{text}\n", encoding="utf-8")
        print(f"Saved {out_md.name} ({len(text)} chars, {status})")
        combined.append(f"\n\n# Batch {batch_id}\n\n{text}")
        written = extract_files(text, layout_dir)
        all_written.extend(written)
        if written:
            print(f"Extracted: {', '.join(written)}")
        if status != "ok":
            print(f"Batch {batch_id} failed — stopping.")
            break

    combined_path = OUT / f"MOONSHOT_HAL_PAGE_DESIGN_ALL_{DATE}.md"
    combined_path.write_text(
        f"# Moonshot HAL Page Design — all batches\n\nKey: {key_name}\n\n{''.join(combined)}\n",
        encoding="utf-8",
    )
    print(f"\nCombined: {combined_path}")
    print(f"Layout files: {sorted(set(all_written))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
