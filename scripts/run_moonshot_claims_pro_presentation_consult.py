"""Moonshot AI — Professional Claims page presentation (vs 3 huge widgets). CONSULT ONLY."""

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
have moonshot ai look at my claims page and make a better suggestion to present claims in a more highly professional manner then 3 huge widgets.
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — product/UX architect for NewRidge Financial 2.0
(NR2 Apex starship-bridge), a Kansas dental S-corp local HTTPS app.

CRITICAL:
1. Answer VERBATIM: look at the Claims page and suggest a BETTER, HIGHLY PROFESSIONAL
   way to present claims than "3 huge widgets."
2. CONSULT ONLY — DO NOT CODE / DO NOT APPLY until operator approves.
3. Ground truth = LIVE FACTS + widget inventory. Never invent claim dollars/IDs/patients.
4. The operator is reacting to visual bulk: three full-width claim-shelf widgets
   (30/60/90) and/or header-stats + giant kanban + risk bars dominating the mosaic.
   Propose a denser, executive, professional RCM presentation.
5. Prefer Apex mosaic patterns; may propose new composite widget types.
6. Rank MUST / SHOULD / NICE. Wireframe in text. Paste-ready spec. Phased plan.
7. Keep HAL control and honesty (empty states, no SoftDent write-back unless asked).

OUTPUT FORMAT (strict markdown):
# Verdict
## 0. Operator Intent (quote; consult-only)
## 1. Critique of Current Claims Page Layout
Why 3 huge widgets feel unprofessional / wasteful.
## 2. Recommended Professional Presentation (primary design)
Layout hierarchy, density, typography, what becomes primary vs secondary.
## 3. Wireframe (text)
First viewport + below-fold.
## 4. Widget / Instrument Spec (CONSULT ONLY)
What to merge, shrink, replace; new composite types if needed.
## 5. Alternatives (2 options) ranked
## 6. Phases + Validation Gate
## 7. Risks & Rollback
DO NOT APPLY until operator approves.
"""


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} lines truncated]"


def build_context() -> str:
    parts: list[str] = []
    for rel, max_lines in (
        ("NewRidgeFinancial2/nr2-build.json", 15),
        ("NewRidgeFinancial2/docs/MOONSHOT_CLAIMS_KANBAN_APPLIED_2026-07-10.md", 50),
        ("NewRidgeFinancial2/docs/MOONSHOT_CLAIMS_MOCKUP_PARITY_CONSULT_2026-07-10.md", 40),
        ("NewRidgeFinancial2/site/apex-bridge.css", 40),
    ):
        path = REPO / rel
        if not path.is_file():
            parts.append(f"### FILE: {rel}\n(missing)")
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        if rel.endswith("apex-bridge.css"):
            # claims-related CSS only
            idx = body.find("Claims aging shelves")
            if idx < 0:
                idx = body.find("apex-claims")
            body = body[max(0, idx) : max(0, idx) + 4500] if idx >= 0 else body[:2000]
        parts.append(f"### FILE: {rel}\n```\n{_truncate(body, max_lines)}\n```")

    backend = REPO / "NewRidgeFinancial2" / "apex_backend.py"
    if backend.is_file():
        text = backend.read_text(encoding="utf-8", errors="replace")
        idx = text.find("def _claims_widgets")
        if idx >= 0:
            parts.append(
                f"### EXCERPT: _claims_widgets\n```python\n{_truncate(text[idx : idx + 5500], 120)}\n```"
            )

    pack = REPO / "NewRidgeFinancial2" / "apex_claims_narratives_pack.py"
    if pack.is_file():
        text = pack.read_text(encoding="utf-8", errors="replace")
        for marker, n in (("def shelf_widget", 40), ("def kanban_widget", 45)):
            i = text.find(marker)
            if i >= 0:
                parts.append(f"### EXCERPT: {marker}\n```python\n{_truncate(text[i : i + 2200], n)}\n```")

    parts.append(
        """### LIVE FACTS (hal-10390 — Claims page inventory)
Claims page currently stacks MANY instruments, including these LARGE full-width ones:
1. import-health-monitor (status, full)
2. KPI row: claims-total, claims-open, claims-denied, claims-aging-count (+ visual boosts)
3. claims-follow-up status
4. ins/patient split
5. THREE huge claim-shelf widgets: claims-aging-30, claims-aging-60, claims-aging-90
   (each size=full, horizontal tile shelves)
6. claims-header-stats (full)
7. claims-kanban-board (full, 5-column workbench — also large)
8. claims-risk-analytics (m)

Operator complaint: presentation feels like "3 huge widgets" — wants HIGHLY PROFESSIONAL
claims presentation, denser/executive, not three giant blocks.

Constraints: SoftDent import-backed; never invent $; read-only SoftDent status;
HAL focus/filter/card actions already exist; Apex mosaic shell.

CONSULT ONLY — suggest better layout; do not code until operator approves.
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
        "CONSULT ONLY — professional presentation recommendations. Do not apply code.\n\n"
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
        headers["X-Title"] = "NR2 Claims Professional Presentation Consult"

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
        f"# Moonshot AI — Professional Claims Presentation (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10390  \n"
        f"**Script:** `scripts/run_moonshot_claims_pro_presentation_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_CLAIMS_PRO_PRESENTATION_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_CLAIMS_PRO_PRESENTATION_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
