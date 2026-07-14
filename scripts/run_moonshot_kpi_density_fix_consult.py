"""Moonshot AI — Too many KPIs appear: how to fix, then re-report (CONSULT ONLY).

Operator request is passed VERBATIM. Do not rewrite operator intent.
Does NOT apply any code. Await operator approval before coding.
"""

from __future__ import annotations

import json
import os
import sys
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

OPERATOR_REQUEST_VERBATIM = "alot of kpis appear ask moonshot ai how to fix and rereport"

SYSTEM = """You are Moonshot AI — principal UX/systems engineer for NR2 Apex HAL
(hal-10561 + hal-local:32b / qwen3:32b Q4_K_M on R9700).

Operator complaint (VERBATIM): "alot of kpis appear" — they want you to
explain HOW TO FIX the KPI overcrowding, THEN RE-REPORT (consult report).

CONSULT ONLY — DO NOT claim you applied code. Await operator approval.

ALREADY SHIPPED (do not pretend missing; build on this):
- Compact professional pages + zero-scroll (hal-10561): maxHeight tiers,
  rowCap 5, collapseWhenEmpty, compact density default, Claims Top5 +
  kanban subpage, HAL chat capped
- Financial Executive Console: command strip + vital-signs (4 pills) +
  charts + secondary KPI row + EBITDA
- Prior Moonshot contract: Strip 2 = 3–4 KPI micro-cards ONLY (prod,
  collections, A/R, alerts) — first viewport cockpit, not warehouse

LIVE KPI EMIT COUNTS (static code scan of apex_backend builders — approx
emit sites, not runtime after collapse):
- _taxes_widgets: ~13 KPI emits  ← worst offender
- _softdent_widgets: ~7
- _quickbooks_widgets: ~6
- _hal_widgets: ~6
- _ar_widgets: ~5
- _office_manager_widgets: ~5
- _documents_widgets: ~5
- _financial_widgets_from_reports: ~4 standalone KPIs PLUS vital-signs
  executive-strip (4 pills) PLUS packs (revenue/EBITDA/etc.)
- _narratives_widgets: ~4
- _library_widgets: ~4
- _claims_widgets: ~3
- apex_subpages_pack.py: ~5

PROBLEM FRAME:
Operator sees "a lot of KPIs" — empty chips still take mosaic slots;
secondary KPIs compete with vitals; Taxes dumps many empty planning KPIs;
zero-scroll capped HEIGHT but not KPI COUNT. Prior compact/zero-scroll
passes did not enforce a hard "≤N visible KPIs above fold" budget.

HONESTY RULES (non-negotiable):
- empty ≠ $0; never invent dollars to fill mosaic
- Prefer collapse / hide / move to subpage / pack into one strip
  over fabricating values
- Prefer Apex additive fixes; real file paths only

REAL PATHS (use these; do not invent trees):
- NewRidgeFinancial2/apex_backend.py (_*_widgets builders, _money_kpi,
  _count_kpi, _empty_kpi)
- NewRidgeFinancial2/apex_financial_console_pack.py (vital-signs,
  command strip, revenue, ebitda)
- NewRidgeFinancial2/apex_compact_pages_pack.py (normalize_first_viewport,
  apply_zero_scroll_contract, collapse_empty_large)
- NewRidgeFinancial2/site/apex-core.js, apex-tokens.css, apex-bridge.css
- NewRidgeFinancial2/docs/MOONSHOT_COMPACT_PROFESSIONAL_PAGES_CONSULT_2026-07-11.md
- NewRidgeFinancial2/docs/MOONSHOT_ZERO_SCROLL_WIDGETS_APPLIED_2026-07-11.md
- NewRidgeFinancial2/docs/MOONSHOT_ZERO_SCROLL_PIXEL_BUDGET_2026-07-11.md

OUTPUT (strict markdown — this IS the re-report):
# Verdict (one sentence — root cause + fix direction)
## 0. Operator Intent (quote verbatim; confirm consult-only)
## 1. Why So Many KPIs Appear (post-hal-10561 diagnosis)
Be blunt: which pages, which builders, empty vs populated, vitals vs
secondary vs tax planning dump
## 2. KPI Density Contract (hard rules)
e.g. max visible KPI tiles above fold; empty KPI → strip/chip or hide;
pack related empties into one status; vitals absorb primary money metrics
## 3. Fix Package (THE recommended work package)
Name, why now, effort, REAL files, phases, validation gate
(1920×1080 compact: ≤N KPIs above fold per page)
## 4. Page-by-Page KPI Map
Table: Page | Current KPI problem | Keep (≤3–4) | Collapse/hide/subpage | Target first viewport
## 5. Report Summary (executive bullets for operator)
## 6. Approval checklist
DO NOT APPLY CODE. Prefer one clear fix package over a laundry list.
"""


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No API key", file=sys.stderr)
        return 1
    model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    if "moonshot" not in (base_url or "").lower():
        model = str(
            os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2"
        ).strip()
    print(f"Using {key_name} @ {base_url} model={model}")

    excerpts: list[str] = []
    for name, lim in (
        ("MOONSHOT_ZERO_SCROLL_WIDGETS_APPLIED_2026-07-11.md", 2000),
        ("MOONSHOT_ZERO_SCROLL_PIXEL_BUDGET_2026-07-11.md", 1500),
        ("MOONSHOT_COMPACT_PROFESSIONAL_PAGES_CONSULT_2026-07-11.md", 2500),
    ):
        p = DOCS / name
        if p.is_file():
            excerpts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')[:lim]}")

    # Snippet of taxes + financial KPI builders for concrete diagnosis
    backend = REPO / "NewRidgeFinancial2" / "apex_backend.py"
    backend_snip = ""
    if backend.is_file():
        t = backend.read_text(encoding="utf-8")
        # financial Level 5 KPIs + taxes start
        i = t.find("# Level 5 — Secondary KPIs")
        j = t.find("def _taxes_widgets")
        k = t.find("def _softdent_widgets")
        if i >= 0 and j >= 0:
            backend_snip += "### apex_backend financial secondary KPIs\n```\n" + t[i : j][:1800] + "\n```\n"
        if j >= 0 and k >= 0:
            backend_snip += "### apex_backend _taxes_widgets (start)\n```\n" + t[j:k][:2200] + "\n```\n"

    user = (
        f"OPERATOR REQUEST (VERBATIM):\n{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Ask Moonshot: a lot of KPIs appear. HOW TO FIX, then RE-REPORT. "
        "CONSULT ONLY — do not apply code.\n\n"
        "Build: hal-10561. Zero-scroll + compact already applied; KPI COUNT "
        "still too high (esp. Taxes ~13 empty/planning KPIs). Prior contract "
        "said 3–4 Strip-2 KPIs — enforce that with collapse/hide/subpage, "
        "not invented dollars.\n\n"
        + backend_snip
        + "\n\n".join(excerpts)
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "temperature": 1.0,
        "max_tokens": 8000,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 KPI Density Fix Consult"
    import urllib.request

    print("Calling Moonshot AI (consult only — will not apply)...")
    req = urllib.request.Request(
        base_url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            content = extract_message_content(json.loads(resp.read().decode()))
        status = "ok"
    except Exception as exc:
        content = str(exc)
        status = "error"

    header = (
        f"# Moonshot AI — KPI Density Fix & Re-Report (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Status:** {status}  \n"
        f"**Build:** hal-10561 + hal-local:32b  \n"
        f"**Prior:** zero-scroll + compact (hal-10561); still too many KPI tiles  \n"
        f"**Script:** `scripts/run_moonshot_kpi_density_fix_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out = OUT / f"MOONSHOT_KPI_DENSITY_FIX_CONSULT_{DATE}.md"
    doc = DOCS / f"MOONSHOT_KPI_DENSITY_FIX_CONSULT_{DATE}.md"
    out.write_text(full, encoding="utf-8")
    doc.write_text(full, encoding="utf-8")
    print(out)
    print(doc)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
