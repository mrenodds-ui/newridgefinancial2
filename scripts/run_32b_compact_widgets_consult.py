"""hal-local:32b CONSULT — Better compact widgets for all pages + report.

Operator: ask 32b if there are better widgets that are compact that would
be better for all pages and report.

CONSULT ONLY — does NOT apply code. Uses only approved local model.
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
OUT.mkdir(parents=True, exist_ok=True)
DOCS.mkdir(parents=True, exist_ok=True)
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

OLLAMA_RAW = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").strip().rstrip("/")
if OLLAMA_RAW and "://" not in OLLAMA_RAW:
    OLLAMA_RAW = f"http://{OLLAMA_RAW}"
OLLAMA = OLLAMA_RAW or "http://127.0.0.1:11434"
MODEL = os.getenv("NR2_32B_MODEL", "hal-local:32b")
# Ollama accepts int (-1 = forever) or duration strings like "30m"
_ka = os.getenv("NR2_32B_KEEP_ALIVE", "-1").strip()
try:
    KEEP_ALIVE: int | str = int(_ka)
except ValueError:
    KEEP_ALIVE = _ka or -1
BROWSER = os.getenv("NR2_BROWSER", "https://127.0.0.1:8765").rstrip("/")
CTX = ssl._create_unverified_context()

OPERATOR_REQUEST_VERBATIM = (
    "ask 32b if there are better widgets that are compact that would be "
    "better for all pages and report"
)

SYSTEM = """You are hal-local:32b (Qwen3 32B Q4_K_M) acting as principal UI/data
engineer for NR2 Apex HAL (BUILD_ID=hal-10608).

Operator asks whether there are BETTER COMPACT widgets that would improve
ALL pages, then produce a REPORT.

CONSULT ONLY — DO NOT claim you applied code. empty ≠ $0. Never invent
SoftDent dollars or write-back.

HARD CONSTRAINTS already in product (honor them):
- Zero-scroll target: page scrollHeight ≈ viewport at 1920×1080 compact density
- Height caps: primary ≤320px, secondary ≤240px, micro ≤120px
- KPI budget ≤4 pills above fold (executive-strip / kpi-micro-strip)
- Empty widgets collapse to strip; never pad empty with $0
- Density default = compact
- Reports: SoftDent Output Options Excel or Print Preview only — never Printer

CURRENT STACK (real):
- apex_compact_pages_pack.py — micro-strip, collapse_empty, height tiers
- apex_better_backend_widgets_pack.py — pareto, radial-gauge, timeline-lanes,
  data-table, tax-calendar, action-list, status-matrix, patient-dossier
- apex_backend.py — page widget builders (financial, ar, claims, taxes, …)
- site/apex-core.js — density, size map (strip/s/m/l/xl/full), renderers
- Widget types in use: kpi, chart, status, executive-strip, financial-command-strip,
  radial-gauge, dual-axis-trend, pareto-chart, timeline-lanes, data-table,
  tax-calendar, waterfall, bullet, scrubber, horizontal-bar, donut, stacked-bar,
  heatmap, funnel, countdown, scenario-manager, filing-workflow, workpaper,
  ai-insight, action-list, collection-task-list, status-matrix, patient-dossier-card, …

GOAL: Recommend a SMALL set of compact widget patterns that can be REUSED
across ALL pages (not one-off page toys), plus how reports should present
the same facts without scrolling.

Prefer:
1) Replace tall full/xl tables/kanbans with strip/tile/micro patterns
2) Cross-page primitives (same chrome on financial/ar/claims/taxes/ops)
3) Honest empty states (warm/empty strip, not fake zeros)
4) Report twin: same KPIs in Print Preview / Excel-friendly summary rows

OUTPUT (strict markdown):
# Verdict (one sentence: yes/no + the compact primitive family to standardize on)
## 0. Operator Intent (verbatim; confirm consult-only)
## 1. Current compact stack — what already works
## 2. Gaps (where pages still waste height / scroll)
## 3. Recommended compact widget set for ALL pages (≤8 primitives; name, size, when to use, when NOT)
## 4. Per-page mapping (financial, ar, claims, taxes, operations/softdent, narratives, documents) — swap tall → compact
## 5. Report twin (Excel / Print Preview summary layout mirroring compact KPIs)
## 6. Coding package if approved later (MUST / SHOULD; real files only; no diffs required unless short)
## 7. What NOT to redo / invent
## 8. Acceptance criteria
## 9. Executive Summary (5 bullets)
## 10. Approval checklist
Be concrete and ranked. Prefer reuse over inventing 20 new chart types.
"""


def _get_json(url: str, timeout: int = 45) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, context=CTX, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _live_context() -> str:
    parts: list[str] = []
    try:
        health = _get_json(f"{BROWSER}/api/health", timeout=8)
        parts.append(
            "### Browser health\n```json\n"
            + json.dumps(
                {
                    k: health.get(k)
                    for k in (
                        "ok",
                        "readinessLevel",
                        "ollama",
                        "importPipeline",
                        "backupLastAt",
                    )
                },
                indent=2,
            )
            + "\n```"
        )
    except Exception as e:
        parts.append(f"### Browser health\n(unavailable: {type(e).__name__}: {e})")

    try:
        census = _get_json(f"{BROWSER}/api/apex/widget-census", timeout=60)
        census_path = OUT / "widget_census_live.json"
        census_path.write_text(json.dumps(census, indent=2), encoding="utf-8")
        pages = census.get("pages") or []
        lines = [
            f"- **{p.get('page')}**: total={p.get('total')} "
            f"withData={p.get('withData')} empty={p.get('empty')}"
            for p in pages
            if isinstance(p, dict)
        ]
        # Keep payload small — sample first page widget type breakdown if present
        type_lines: list[str] = []
        for p in pages:
            if not isinstance(p, dict):
                continue
            widgets = p.get("widgets") or []
            if not isinstance(widgets, list):
                continue
            from collections import Counter

            c = Counter()
            for w in widgets:
                if isinstance(w, dict):
                    c[str(w.get("type") or "?")] += 1
            if c:
                top = ", ".join(f"{t}:{n}" for t, n in c.most_common(12))
                type_lines.append(f"- **{p.get('page')} types**: {top}")
        parts.append(
            "### Live widget census (all pages)\n"
            + ("\n".join(lines) if lines else "(no pages)")
            + ("\n\n" + "\n".join(type_lines) if type_lines else "")
        )
    except Exception as e:
        parts.append(f"### Live widget census\n(unavailable: {type(e).__name__}: {e})")

    # Snippets from compact pack + zero-scroll consult
    for rel, start, n in (
        ("NewRidgeFinancial2/apex_compact_pages_pack.py", 0, 100),
        ("NewRidgeFinancial2/docs/MOONSHOT_ZERO_SCROLL_WIDGETS_CONSULT_2026-07-11.md", 0, 80),
        ("NewRidgeFinancial2/docs/MOONSHOT_KPI_DENSITY_FIX_CONSULT_2026-07-12.md", 0, 40),
    ):
        path = REPO / rel
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            chunk = "\n".join(lines[start : start + n])
            parts.append(f"### {rel} (excerpt)\n```\n{chunk[:3500]}\n```")

    return "\n\n".join(parts)


def _ollama_chat(messages: list[dict], *, num_predict: int = 4200) -> str:
    payload = {
        "model": MODEL,
        "stream": False,
        "keep_alive": KEEP_ALIVE,
        "messages": messages,
        "options": {
            "temperature": 0.2,
            "num_predict": num_predict,
            "num_ctx": 8192,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        body = json.loads(resp.read().decode("utf-8", errors="replace"))
    msg = body.get("message") or {}
    content = msg.get("content") or ""
    # Qwen3 sometimes puts reasoning in thinking; prefer content
    if not str(content).strip() and msg.get("thinking"):
        content = msg.get("thinking")
    return str(content).strip()


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = OUT / f"32b_compact_widgets_raw_{stamp}.json"
    doc_path = DOCS / f"HAL_32B_COMPACT_WIDGETS_CONSULT_{DATE}.md"

    print(f"model={MODEL} ollama={OLLAMA}", flush=True)
    live = _live_context()
    user = (
        f"Operator request (verbatim):\n> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"Live + code context:\n{live}\n\n"
        "Produce the full markdown report now (consult only)."
    )

    try:
        content = _ollama_chat(
            [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ]
        )
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:800]
        print(f"HTTPError {e.code}: {err}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1

    raw_path.write_text(
        json.dumps(
            {
                "model": MODEL,
                "date": DATE,
                "operator": OPERATOR_REQUEST_VERBATIM,
                "content": content,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    header = (
        f"# HAL 32B — Compact widgets for all pages (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}\n"
        f"**Model:** `{MODEL}`\n"
        f"**Build:** hal-10608\n"
        f"**Script:** `scripts/run_32b_compact_widgets_consult.py`\n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    doc_path.write_text(header + content + "\n", encoding="utf-8")
    print(f"wrote {doc_path}", flush=True)
    print(f"wrote {raw_path}", flush=True)
    print("--- REPORT PREVIEW ---", flush=True)
    print(content[:6000], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
