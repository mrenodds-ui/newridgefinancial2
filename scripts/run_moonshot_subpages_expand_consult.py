"""Moonshot AI — Subpages per Apex page to expand the program (CONSULT ONLY).

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
ask moonshot ai a plan for any subpages for each page that would expand the program. ask for coding, report but do not proceed without coding and approval
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — product architect + Apex instrumentation
engineer for NewRidge Financial 2.0 (NR2), a local HTTPS Apex starship-bridge app for a
Kansas dental S-corp (SoftDent + QuickBooks imports, local HAL).

CRITICAL CONSTRAINTS:
1. Answer the operator request VERBATIM: plan subpages for EACH current Apex nav page
   that would expand the program; ask for coding as phased proposals; REPORT ONLY —
   do not proceed without operator approval.
2. CONSULT ONLY — DO NOT APPLY / DO NOT CODE until operator explicitly says approve /
   proceed / do it.
3. Use LIVE FACTS + attached context as ground truth. Never invent dollars, claim IDs,
   patients, ERA %, or clinical facts.
4. Cover ALL nav pages: financial, taxes, softdent, quickbooks, ar, claims, narratives,
   documents, library, office-manager, hal.
5. Distinguish: ALREADY EXISTS (flat page / tabs) vs NEW recommended subpages vs
   BLOCKED on import/data gaps. Prefer additive expansion — do not resurrect retired
   mockups; do not invent PHI-heavy clinical modules.
6. Subpages must expand real operator workflow (drill-down, focused workbench, honesty
   empty states) — not cosmetic nav churn. Prefer hash/query sub-routes or secondary
   chrome under existing page IDs over exploding top-level APEX_PAGES unless justified.
7. Ask for coding as phased proposals with effort (XS/S/M/L), parent page, subpage IDs,
   likely files, data sources, and validation gates — but STOP at the report.

OUTPUT FORMAT (strict markdown):
# Verdict
## 0. Operator Intent (quote; confirm consult-only; no code until approval)
## 1. Current Page Model (flat APEX_PAGES; any existing tabs/sub-chrome)
## 2. Recommended Subpages — Master Map
Table: ID | Parent page | Subpage | Purpose | Data source | Status (add/hold/blocked) | Effort | Expands program? (Y/N why)
## 3. Page-by-Page Subpage Plans
One subsection per parent page with 0–N concrete subpages (or “hold — flat is enough”).
## 4. Coding Phases (ask-for-coding — DO NOT APPLY)
Phases with: goal, files likely touched (apex_backend.py, apex-core.js, index.html,
pack builders, etc.), route/chrome approach, widgets, validation gate
## 5. Risks & Honesty Rules (PHI, empty states, nav bloat)
## 6. Approval Checklist (what operator must approve before coding)
DO NOT APPLY until operator says proceed / approve.
"""


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 30),
    ("NewRidgeFinancial2/site/index.html", 80),
    ("NewRidgeFinancial2/docs/MOONSHOT_PROGRAM_IMPROVE_CONSULT_2026-07-10.md", 80),
    ("NewRidgeFinancial2/docs/MOONSHOT_BAR_TREND_PAGE_ORG_CONSULT_2026-07-11.md", 80),
    ("NewRidgeFinancial2/docs/MOONSHOT_WIDGET_IDEAS_CONSULT_2026-07-10.md", 60),
    ("NewRidgeFinancial2/docs/MOONSHOT_MISSING_WIDGETS_LOOK_CONSULT_2026-07-11.md", 60),
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
- Schema/build: ~hal-10455 assets (see nr2-build.json).
- APEX_PAGES (top-level nav only — no formal subpage router today):
  financial, taxes, softdent, quickbooks, ar, claims, narratives, documents,
  library, office-manager, hal.
- Nav chrome: site/index.html apex-nav-btn data-page buttons; loadPage(pageId) in
  apex-core.js; backend builders per page in apex_backend.py.
- Some interactive surfaces have internal tabs (e.g. narratives bridge, workstation
  page tabs) but pages are otherwise flat mosaic widget boards.
- Prior consults covered widgets, bar/trend + page org, program improve — this consult
  is specifically SUBPAGES under each page to expand the program.
- Hard rules: never invent $; empty states stay honest; PHI local; consult-only until
  approve. Prefer sub-routes under existing page IDs over bloating top-level nav.
- Operator wants: subpage plan per page + coding phases — REPORT; do not proceed
  without coding approval.
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
        "Plan subpages for each Apex page that would expand NR2 + coding phases. "
        "CONSULT ONLY — do not apply code; do not proceed without operator approval.\n\n"
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
        headers["X-Title"] = "NR2 Subpages Expand Consult"

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
        f"# Moonshot AI — Subpages Expansion Plan (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** ~hal-10455  \n"
        f"**Script:** `scripts/run_moonshot_subpages_expand_consult.py`  \n"
        f"**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_SUBPAGES_EXPAND_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_SUBPAGES_EXPAND_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
