"""Moonshot AI — Starship bridge UI critique of live NR2-Apex (CONSULT ONLY).

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

# Operator words — DO NOT REWRITE
OPERATOR_REQUEST_VERBATIM = """
no have moonshot look at the current setup, the widgets are elongated unoranized.  i need widgets animated looking like a futurist high tech outlay, scrolling ticker tape with information, a side bar, interactive naritive page,  looking like a highly scientic progrofession financial pages that belong on a travelling starv ship
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — lead product architect + starship-bridge UI designer
for NewRidge Financial 2.0 (NR2), a solo dental practice financial cockpit on Windows.

CRITICAL CONSTRAINTS FROM OPERATOR (obey exactly; do not soften or reinterpret):
1. Look at the CURRENT Apex setup (hal-10220) — critique what is wrong NOW.
2. Widgets are elongated / unorganized — fix that with a real layout system (not more stretchy auto-fit cards).
3. Widgets must be animated and look like a futurist high-tech outlay.
4. Scrolling ticker tape with information is REQUIRED.
5. A side bar is REQUIRED.
6. Interactive narrative page is REQUIRED.
7. Pages must look like highly scientific / professional financial pages that belong on a travelling starship.
8. Provide CODE + REPORT.
9. CONSULT ONLY — DO NOT APPLY until operator validates.
10. Do not rewrite what the operator wants — treat their wording as the source of truth.

Current live facts (hal-10220 NR2-Apex after P0–P5):
- Shell: site/index.html + apex-tokens.css + apex-animations.css + apex-core.js + apex-hal-bridge.js
- Layout today: sticky top nav of 11 page buttons + auto-fit CSS grid (minmax(140px, 1fr))
- Problem operator sees: widgets stretch wide/elongated, feel unorganized, not starship-bridge density
- Backend: /api/apex/widgets/<page>, /api/apex/hal/status, /api/apex/print/, /api/apex/sync/trigger
- Honest empty states; never invent dollar amounts
- HAL chat already on right rail for HAL page only — operator wants a real sidebar + ticker for ALL pages
- Narratives page today is weak KPI stubs — operator wants INTERACTIVE narrative page

HARD RULES FOR YOUR RESPONSE:
- CONSULT ONLY. Explicitly state: wait for operator validation before any apply.
- Critique CURRENT layout failures first (elongation, organization, missing ticker/sidebar/starship feel).
- Propose a STARSHIP BRIDGE layout: fixed sidebar, top/bottom ticker tape, dense instrument widgets (fixed sizes, not stretchy), scientific telemetry aesthetic.
- Interactive Narratives: concrete interaction model (timeline scrubber, section jump, HAL-assisted rewrite, print packet) — not another KPI grid.
- Animation budget: intentional (ticker scroll, widget boot sequence, sidebar pulse, chart draw) — not noise.
- Paste-ready foundation code for: (a) bridge shell HTML, (b) CSS for sidebar+ticker+fixed widget mosaic, (c) ticker JS fed by backend, (d) interactive narratives page scaffold, (e) backend ticker/narrative feed helpers.
- Keep wipe-safe: do NOT resurrect moonshot-mockup / live-wire overlays. Evolve Apex shell forward.
- Never invent financial dollar amounts in sample data — use null/empty or clearly labeled PLACEHOLDER structure.

OUTPUT FORMAT (strict markdown):
# Verdict
## 0. Operator Intent (quote request; confirm no rewrite)
## 1. Current Setup Critique (why elongated / unorganized / not starship)
## 2. Target Starship Bridge Layout
Sidebar, ticker tape, stage mosaic, header/status — wireframe in text + CSS grid/flex rules.
## 3. Widget System Redesign
Fixed sizes, density, animation, organization rules (no stretchy auto-fit elongation).
## 4. Scrolling Ticker Tape Spec
Content sources, scroll behavior, backend feed, accessibility (prefers-reduced-motion).
## 5. Sidebar Spec
Nav + HAL status + quick actions; always present across pages.
## 6. Interactive Narratives Page
Interaction model, widgets/panels, backend helpers.
## 7. Scientific / Starship Visual Language
Tokens, typography, motion, instrumentation chrome (without purple-glow cliché overload).
## 8. Moonshot Code Deliverables (paste-ready)
### File: ...
```language
...
```
## 9. Implementation Phases (S0→Sn) + Validation Gate
DO NOT APPLY until operator says proceed/validated.
## 10. Risks & Rollback
"""


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 20),
    ("NewRidgeFinancial2/site/index.html", 60),
    ("NewRidgeFinancial2/site/apex-tokens.css", 120),
    ("NewRidgeFinancial2/site/apex-animations.css", 80),
    ("NewRidgeFinancial2/site/apex-core.js", 100),
    ("NewRidgeFinancial2/site/apex-hal-bridge.js", 80),
    ("NewRidgeFinancial2/docs/_consult_scratch/apex_current_snapshot.json", 200),
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

    # Visual/layout diagnosis notes from live CSS
    parts.append(
        """### LIVE LAYOUT DIAGNOSIS (operator complaint mapped to code)
- `.apex-grid` uses `grid-template-columns: repeat(auto-fit, minmax(var(--apex-widget-min), 1fr));`
  with `--apex-widget-min: 140px` → widgets STRETCH to fill row width → elongated look.
- `.apex-widget--wide { grid-column: span 2; }` makes charts even wider.
- Top horizontal nav wraps 11 buttons — no persistent left/right sidebar on financial pages.
- No ticker tape element exists in index.html.
- Narratives page returns ~4 KPI/status widgets only — not interactive narrative UI.
- Motion exists (apexEnter, halPulse, suggestion panel) but layout organization is still a flat stretchy mosaic.
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
        "Build under review: hal-10220 (NR2-Apex P0–P5). Live app NewRidgeFinancial2 only.\n"
        "Critique current elongated/unorganized widgets. Deliver starship-bridge redesign plan + foundation code.\n"
        "CONSULT ONLY — do not apply.\n\n"
        "## Codebase + live snapshot context\n\n"
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
        headers["X-Title"] = "NR2 Starship Bridge UI Consult"

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
        f"# Moonshot AI — Starship Bridge UI Critique (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10220  \n"
        f"**Script:** `scripts/run_moonshot_starship_bridge_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator validates.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_STARSHIP_BRIDGE_UI_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_STARSHIP_BRIDGE_UI_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
