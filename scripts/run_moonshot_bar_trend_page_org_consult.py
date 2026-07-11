"""Moonshot AI — Bar/trend graphs + page organization (CONSULT ONLY).

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
aks moonshot ai is there any bar and trend graph that can be placed in the program and orgranize the pages better and ask for coding, report until approved
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — product architect + Apex instrumentation
engineer for NewRidge Financial 2.0 (NR2), a local HTTPS Apex starship-bridge app for a
Kansas dental S-corp (SoftDent + QuickBooks imports, local HAL).

CRITICAL CONSTRAINTS:
1. Answer the operator request VERBATIM: (a) which bar and trend graphs can be placed in
   the program, (b) how to organize pages better, (c) propose coding phases —
   REPORT ONLY until operator approves.
2. CONSULT ONLY — DO NOT APPLY / DO NOT CODE until operator explicitly says approve /
   proceed / do it.
3. Use LIVE FACTS + attached context as ground truth. Never invent dollars, claim IDs,
   patients, ERA %, or clinical facts. Prefer import-backed series only.
4. Prefer Apex-native instruments (already supported types: chart/bar/line,
   horizontal-bar, stacked-bar, dual-axis-trend, donut) over third-party embeds.
5. Do not resurrect retired mockups. Additive improvements to current pages.
6. Distinguish: ALREADY SHIPPED charts vs NEW recommended charts vs NEED MORE IMPORT DATA.
7. Page organization must respect current nav pages: financial, taxes, softdent,
   quickbooks, ar, claims, narratives, documents, library, office-manager, hal.
8. Ask for coding as phased proposals with effort (XS/S/M/L), page targets, instrument
   types, data sources, and validation gates — but STOP at the report.

OUTPUT FORMAT (strict markdown):
# Verdict
## 0. Operator Intent (quote; confirm consult-only)
## 1. Already-Shipped Bar & Trend Graphs (inventory by page)
## 2. Recommended NEW Bar & Trend Graphs (placeable now vs blocked on imports)
Table: ID | Chart | Type | Page | Data source | Status (ship/add/blocked) | Effort
## 3. Page Organization Plan (before/after map; what moves where; why)
## 4. Coding Phases (ask-for-coding — DO NOT APPLY)
Phases with: goal, files likely touched, widgets, validation gate
## 5. Risks & Honesty Rules
## 6. Approval Checklist (what operator must approve before coding)
DO NOT APPLY until operator says proceed / approve.
"""


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 30),
    ("NewRidgeFinancial2/docs/MOONSHOT_FINANCIAL_PRO_PRESENTATION_CONSULT_2026-07-10.md", 100),
    ("NewRidgeFinancial2/docs/MOONSHOT_PROGRAM_IMPROVE_CONSULT_2026-07-10.md", 80),
    ("NewRidgeFinancial2/docs/MOONSHOT_WIDGET_IDEAS_CONSULT_2026-07-10.md", 60),
    ("NewRidgeFinancial2/apex_financial_console_pack.py", 80),
    ("NewRidgeFinancial2/site/index.html", 60),
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
        """### LIVE FACTS (consult time 2026-07-11)
- App: local HTTPS Apex Bridge https://127.0.0.1:8765/ (TLS required).
- Schema/build: ~hal-10447 assets; financial Executive Console (hal-10430+) packed top-down.
- Pages (nav): financial, taxes, softdent, quickbooks, ar, claims, narratives, documents,
  library, office-manager, HAL.
- Chart instrument types already in Apex JS/backend:
  - type chart|bar|line (+ chartType bar/line) via ApexChartWidget canvas
  - horizontal-bar (provider / QB expense)
  - stacked-bar (ins vs patient / similar)
  - dual-axis-trend (production vs collections pulse)
  - donut (payer mix when data exists)
- Financial page already places: dual-axis-trend, provider-hbar, ar-aging-chart (bar),
  revenue-composition (often empty pending SoftDent Collections/Daysheet for period).
- Widget silent auto-refresh just changed from 30s → 30 minutes (operator request) to
  stop page flicker.
- HAL chat rail narrowed ~1/3; HAL 403 session retry fixed earlier.
- Hard rules: never invent $; empty charts stay honest; PHI local; consult-only until approve.
- Operator wants: more/better bar+trend graphs across the program, better page org,
  coding plan — REPORT until approved.
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
        "Recommend bar/trend graphs placeable in NR2-Apex + better page organization + "
        "coding phases. CONSULT ONLY — do not apply code.\n\n"
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
        "max_tokens": 12000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Bar Trend Page Org Consult"

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
        f"# Moonshot AI — Bar/Trend Graphs + Page Organization (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** ~hal-10447  \n"
        f"**Script:** `scripts/run_moonshot_bar_trend_page_org_consult.py`  \n"
        f"**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_BAR_TREND_PAGE_ORG_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_BAR_TREND_PAGE_ORG_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
