"""Moonshot AI — COMPLETE high-tech redesign plan (CONSULT ONLY — no apply).

Operator request is passed VERBATIM. Do not rewrite operator intent.
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

# API helper was archived with .local_logs during cleanup
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

# Operator words — DO NOT REWRITE
OPERATOR_REQUEST_VERBATIM = """
i dont want a mock up but a complete high tech redesign of the entire program wilf smal widgets of graphs charts and icon like print buttons, to remove current layout and a detailed plan from start to fish on how to do it.  i want it to look highly high tech professional with a detailed futuristic presentation wih anything animated and automated.  problem is i dont want overlays, old legacry rearrangement.  i want that wiped out before laying down a new design.  i believe past inknown programs were interfereing.  if i need a backend do it and replace it with functions that help the frontend.  plsease have him give code, report and dont proceed until validated.  do not rewrite what i want.
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — lead product architect + front-end systems designer
for NewRidge Financial 2.0 (NR2), a solo dental practice financial cockpit on Windows.

CRITICAL CONSTRAINTS FROM OPERATOR (obey exactly; do not soften or reinterpret):
1. NOT a mockup. Complete high-tech REDESIGN of the ENTIRE program.
2. Small widgets: graphs, charts, icon actions (e.g. print buttons).
3. REMOVE the current layout. Detailed plan from START TO FINISH.
4. Highly high-tech professional, detailed futuristic presentation; animated + automated.
5. NO overlays. NO old legacy rearrangement. WIPE OUT current design BEFORE laying new design.
6. Past unknown programs were interfering — account for that in the wipe plan.
7. If a backend is needed, design/replace it with functions that HELP THE FRONTEND.
8. Provide CODE + REPORT.
9. DO NOT PROCEED / DO NOT APPLY — consult and plan only until operator validates.
10. Do not rewrite what the operator wants — treat their wording as the source of truth.

Current live stack (facts for planning):
- NewRidgeFinancial2/: Python Bottle browser_app.py on https://127.0.0.1:8765/
- Workstation on 8766 (pywebview)
- site/: vanilla JS (PageSchema, PageCanvas, MoonshotLayoutEngine, HAL canvas)
- Build epoch still labeled moonshot-mockup / live-wire-pilot — operator wants this design language WIPED
- SoftDent + QuickBooks imports, SQLite, local Ollama HAL
- Legacy frontend/app/_legacy already archived off hot path

HARD RULES FOR YOUR RESPONSE:
- CONSULT ONLY. Explicitly state: wait for operator validation before any apply.
- Plan must be wipe-first: list exact files/CSS/JS/layout engines to DELETE or retire BEFORE new UI.
- No "rearrange existing mockup panels" approach. New design system from zero on a clean shell.
- Small widget density: charts/graphs/icons; print and action icons as first-class controls.
- Animation + automation: intentional motion + automated refresh/import/HAL behaviors.
- Backend: propose API functions that serve the new frontend (widget feed, chart series, print packets, HAL).
- Paste-ready code samples for foundation pieces (CSS design tokens, shell HTML/JS, sample widget, sample API route).
- Mark phases P0→Pn with acceptance criteria and validation gates.

OUTPUT FORMAT (strict markdown):
# Verdict
## 0. Operator Intent (quote their request; confirm you will not mockup-rearrange)
## 1. Wipe Plan — remove current layout / overlays / legacy interference
Exact paths to delete, disable, or stop loading (CSS, JS, layout engines, mock-embed, elite overlays).
## 2. Interference & Unknown Program Risks
What could still interfere (ports, old copies, dual layout engines) and how wipe eliminates it.
## 3. Target Design System (futuristic high-tech)
Tokens, typography, density, small widgets, charts, icon buttons, motion/automation budget.
## 4. End-to-End Plan (Start → Finish)
Phased roadmap. Each phase: goal, files touched, wipe vs build, acceptance criteria, STOP for validation.
## 5. Backend Functions That Help the Frontend
New/replaced API routes and payloads for widgets/charts/print/HAL automation.
## 6. Moonshot Code Deliverables (paste-ready foundations)
### File: ...
```language
...
```
Minimum: (a) clean app shell, (b) design-token CSS, (c) one small chart widget, (d) print icon control,
(e) one backend helper route/function. Label as FOUNDATION ONLY — not full program rewrite in one shot.
## 7. Full Program Page Map
financial, taxes, softdent, quickbooks, ar, claims, narratives, documents, library, office-manager, hal —
what each becomes under the new system (small widgets + charts + icons).
## 8. Validation Gate (operator must approve before any apply)
Checklist. Explicit: DO NOT APPLY until operator says proceed/validated.
## 9. Risks & Rollback
"""


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 40),
    ("NewRidgeFinancial2/site/index.html", 80),
    ("NewRidgeFinancial2/site/moonshot-page-registry.js", 120),
    ("NewRidgeFinancial2/site/page-views.js", 80),
    ("NewRidgeFinancial2/site/hal-page.js", 80),
    ("NewRidgeFinancial2/site/hal-page-canvas.js", 80),
    ("NewRidgeFinancial2/site/nr2-moonshot-mockup-chrome.js", 80),
    ("NewRidgeFinancial2/browser_app.py", 60),
    ("NewRidgeFinancial2/nr2_http_server.py", 80),
    ("StartProgram.bat", 20),
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
    # List site CSS/JS that currently drive layout (for wipe inventory)
    site = REPO / "NewRidgeFinancial2" / "site"
    if site.is_dir():
        names = sorted(
            p.name
            for p in site.iterdir()
            if p.suffix in {".js", ".css"} and p.is_file()
        )
        parts.append("### SITE JS/CSS INVENTORY\n```\n" + "\n".join(names) + "\n```")
    return "\n\n".join(parts)


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No Moonshot/OpenRouter API key.", file=sys.stderr)
        return 1

    if "moonshot" in (base_url or "").lower():
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    else:
        model = str(os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2").strip()

    print(f"Using {key_name} @ {base_url} model={model}")
    user = (
        "OPERATOR REQUEST (VERBATIM — do not rewrite):\n\n"
        f"{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Build: hal-10170. Live app NewRidgeFinancial2 only. Legacy stacks archived.\n"
        "Deliver wipe-first complete redesign plan + foundation code. CONSULT ONLY.\n\n"
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
        "max_tokens": 16000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Complete High-Tech Redesign Consult"

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
        f"# Moonshot AI — Complete High-Tech Redesign Plan (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Script:** `scripts/run_moonshot_complete_redesign_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator validates.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_COMPLETE_REDESIGN_PLAN_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_COMPLETE_REDESIGN_PLAN_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
