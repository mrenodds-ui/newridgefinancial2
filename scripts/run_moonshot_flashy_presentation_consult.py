"""Moonshot AI — Flashy high-tech presentation + HAL brain display (CONSULT ONLY).

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
ask moonshot ai are there any flashy presentation additions that can be added all pages that make the pages look high tech.  and on hals page a flasy display that would look like hals brain thinking.
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — starship-bridge UI designer for NewRidge Financial 2.0 (NR2).

CRITICAL CONSTRAINTS:
1. Answer: flashy presentation additions for ALL pages to look high-tech, PLUS a flashy HAL-page display that looks like HAL's brain thinking.
2. Do not rewrite the operator's request — treat their wording as source of truth.
3. CONSULT ONLY — DO NOT APPLY until operator validates.
4. Current live UI is NR2-Apex starship bridge (hal-10250): left sidebar, top ticker, fixed mosaic instruments, interactive narratives, visual-boost widgets (pulse/funnel/heatmap/calculator). Cyan/amber/magenta on void black. Vanilla JS + CSS only.
5. Keep wipe-safe: do NOT resurrect moonshot-mockup / live-wire overlays. Evolve Apex bridge forward.
6. Prefer CSS/canvas/SVG motion that is intentional (presence + hierarchy), not noise. Respect prefers-reduced-motion.
7. Avoid purple-glow cliché overload; stay scientific starship / HAL aesthetic.
8. Never invent financial dollar amounts in sample payloads.
9. Provide paste-ready foundation code for: (a) global flashy chrome CSS, (b) optional shared JS motion helper, (c) HAL brain-thinking display (HTML/CSS/JS) for the HAL page only.
10. Rank ideas by impact vs risk (perf, distraction, accessibility).

OUTPUT FORMAT (strict markdown):
# Verdict
## 0. Operator Intent (quote; confirm consult-only)
## 1. Global Flashy Additions (all pages)
Ranked list with what/where/why; mark MUST / SHOULD / NICE.
## 2. HAL Brain Thinking Display
Concept, placement on HAL page, states (idle/thinking/reply), motion language.
## 3. Moonshot Code Deliverables (paste-ready)
### File: ...
```language
...
```
## 4. Implementation Phases (F0 validate → Fn) + Validation Gate
DO NOT APPLY until operator says proceed/validated.
## 5. Risks (perf, a11y, distraction) & Rollback
"""


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 20),
    ("NewRidgeFinancial2/site/index.html", 90),
    ("NewRidgeFinancial2/site/apex-bridge.css", 80),
    ("NewRidgeFinancial2/site/apex-animations.css", 60),
    ("NewRidgeFinancial2/docs/MOONSHOT_VISUAL_BOOST_APPLIED_2026-07-10.md", 40),
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
        """### LIVE FACTS
- Build: hal-10250 NR2-Apex bridge
- HAL page: right-rail chat + mosaic status widgets
- Motion already: ticker scroll, instBoot, scanlines on hover, HAL orb pulse, suggestion panel
- Operator wants MORE flashy high-tech presentation globally + HAL brain thinking display
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
        "CONSULT ONLY — do not apply. Deliver flashy global presentation ideas + HAL brain display with code.\n\n"
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
        "max_tokens": 12000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Flashy Presentation Consult"

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
        f"# Moonshot AI — Flashy Presentation + HAL Brain (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10250  \n"
        f"**Script:** `scripts/run_moonshot_flashy_presentation_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator validates.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_FLASHY_PRESENTATION_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_FLASHY_PRESENTATION_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
