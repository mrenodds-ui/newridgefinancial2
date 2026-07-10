"""Moonshot AI — Financial page pro design + empty widgets + HAL/program review.

CONSULT ONLY — do not apply code until operator approves.
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
ask moonshot ai to look at my financial page.  i have 3 large widgets with nothgin in them. can he recommend a better more professional design and have him look over the program and hal.  the widgets are not being importated with data.
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — product/UX architect + HAL systems engineer
for NewRidge Financial 2.0 (NR2 Apex starship-bridge), a Kansas dental S-corp local HTTPS app
(SoftDent + QuickBooks imports, local HAL).

CRITICAL:
1. Answer VERBATIM: look at the Financial page (3 large empty/sparse widgets), recommend a
   BETTER MORE PROFESSIONAL design, AND look over the program + HAL. Also diagnose why
   widgets are not being populated from imports.
2. CONSULT ONLY — DO NOT CODE / DO NOT APPLY until operator approves.
3. Ground truth = LIVE FACTS + attached context. Never invent dollars, claim IDs, patients,
   ERA %, or clinical facts.
4. Operator is reacting to visual bulk + empty large instruments on Financial (similar pain
   to Claims' "3 huge widgets"). Prefer denser executive mosaic; may propose merge/shrink/
   composite widgets.
5. Cover: (A) Financial layout redesign, (B) import-data root cause for empty widgets,
   (C) program + HAL review (strengths, gaps, ranked improvements).
6. Rank MUST / SHOULD / NICE. Wireframe in text. Paste-ready widget spec. Phased plan.
7. Keep honesty: empty states when imports missing; SoftDent read-only; no invented $.

OUTPUT FORMAT (strict markdown):
# Verdict
## 0. Operator Intent (quote; consult-only)
## 1. Critique of Current Financial Page (why large empty widgets feel unprofessional)
## 2. Why Widgets Are Empty — Import / Data Root Cause
Map each empty LARGE widget to missing SoftDent/QB field or honesty gate.
## 3. Recommended Professional Financial Presentation (primary design)
Layout hierarchy, density, what to merge/shrink/replace.
## 4. Wireframe (text) — first viewport + below-fold
## 5. Widget / Instrument Spec (CONSULT ONLY)
## 6. Program + HAL Review
Strengths, gaps, HAL board-actions / honesty / proactive gaps.
## 7. Alternatives (2 options) ranked
## 8. Phases + Validation Gate
## 9. Risks & Rollback
DO NOT APPLY until operator approves.
"""


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} lines truncated]"


def _live_financial_inventory() -> str:
    """Build live widget census from apex_backend (import-backed)."""
    nr2 = REPO / "NewRidgeFinancial2"
    sys.path.insert(0, str(nr2))
    try:
        from apex_backend import BUILD_ID, build_apex_widgets, build_page_widget_census

        census = build_page_widget_census("financial")
        payload = build_apex_widgets("financial")
        widgets = payload.get("widgets") or []
        lines = [
            f"Build: {BUILD_ID}",
            f"Census: {census.get('census')}",
            "",
            "Widget inventory (id | size | status | emptyMessage | hint):",
        ]
        for w in widgets:
            if not isinstance(w, dict):
                continue
            lines.append(
                f"- {w.get('id')} | size={w.get('size') or 'default'} | "
                f"status={w.get('status') or 'ok'} | "
                f"empty={w.get('emptyMessage') or ''} | "
                f"hint={(w.get('hint') or '')[:120]}"
            )
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"(live inventory failed: {exc})"


def build_context() -> str:
    parts: list[str] = []
    for rel, max_lines in (
        ("NewRidgeFinancial2/nr2-build.json", 15),
        ("NewRidgeFinancial2/docs/MOONSHOT_CLAIMS_PRO_PRESENTATION_CONSULT_2026-07-10.md", 50),
        ("NewRidgeFinancial2/docs/MOONSHOT_PROGRAM_IMPROVE_CONSULT_2026-07-10.md", 60),
        ("NewRidgeFinancial2/docs/MOONSHOT_DESKTOP_HAL_TAX_EBITDA_CONSULT_2026-07-10.md", 40),
        ("NewRidgeFinancial2/docs/MOONSHOT_MORE_WIDGETS_FLASH_CONSULT_2026-07-10.md", 40),
    ):
        path = REPO / rel
        if not path.is_file():
            parts.append(f"### FILE: {rel}\n(missing)")
            continue
        body = _truncate(path.read_text(encoding="utf-8", errors="replace"), max_lines)
        parts.append(f"### FILE: {rel}\n```\n{body}\n```")

    backend = REPO / "NewRidgeFinancial2" / "apex_backend.py"
    if backend.is_file():
        text = backend.read_text(encoding="utf-8", errors="replace")
        for marker, n in (
            ("def _visual_boost_financial", 80),
            ("def _financial_widgets_from_reports", 120),
            ("def build_payer_donut", 50),
            ("def build_ins_patient_split", 40),
            ("def build_provider_horizontal_bars", 35),
            ("def build_ebitda_waterfall", 40),
            ("def resolve_hal_board_actions", 40),
        ):
            idx = text.find(marker)
            if idx >= 0:
                parts.append(
                    f"### EXCERPT: {marker}\n```python\n{_truncate(text[idx : idx + 4500], n)}\n```"
                )

    parts.append("### LIVE FINANCIAL PAGE INVENTORY (hal-10420)\n```\n" + _live_financial_inventory() + "\n```")

    parts.append(
        """### OPERATOR PAIN (grounded)
Financial page currently stacks many instruments including LARGE ones:
- import-freshness (full), financial-period-scrubber (full)
- liquidity-pulse (l), provider-hbar (l), payer-donut (l), ins-patient-split (l)
- ebitda-waterfall (xl), ebitda-scrubber (full), ebitda-trend (l)

LIVE empty (at consult time): collections-mtd, prod-trend (census), payer-donut,
ins-patient-split — with honesty hints about collectionsPending / missing payer split /
need SoftDent claims with Payer.

Operator sees ~3 large empty/sparse widgets and wants:
1) more professional Financial design (not giant empty boxes)
2) program + HAL review
3) diagnosis: widgets not imported with data

Constraints: SoftDent/QB import-backed; never invent $; SoftDent read-only;
HAL board-actions exist; Apex mosaic shell; Claims already got Executive RCM Console
treatment — Financial should get analogous professional density.

CONSULT ONLY — suggest better layout + import fixes + HAL/program notes; do not code.
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
        "CONSULT ONLY — professional Financial redesign + import diagnosis + program/HAL review. "
        "Do not apply code.\n\n"
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
        "max_tokens": 16000,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if "openrouter" in base_url.lower():
        headers["HTTP-Referer"] = "https://github.com/NewRidgeFamilyFinancial"
        headers["X-Title"] = "NR2 Financial Professional Presentation Consult"

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
        f"# Moonshot AI — Financial Pro Presentation + Program/HAL Review (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10420  \n"
        f"**Script:** `scripts/run_moonshot_financial_pro_presentation_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_FINANCIAL_PRO_PRESENTATION_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_FINANCIAL_PRO_PRESENTATION_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
