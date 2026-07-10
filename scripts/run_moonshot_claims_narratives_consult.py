"""Moonshot AI — Claims aging tile rows + Narratives clinical/claims/insurance HAL (CONSULT ONLY).

Operator request is passed VERBATIM. Do not rewrite operator intent.
Does NOT apply any code. Await operator approval before Moonshot/implementation coding.
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
ask moonshot ai to design the claims page with rows of 30 day claims, 60 day claims, 90 day claims widget that line of boxes, when clicked brings up the actual claim, the claim box should be a box with the claim id, patient name and date.  this widget hal also has control, I need also the narative page to have access to clinical notes, claims, insurance informaton and expand ability to have hal produce naratives to inurance companies.  if he has any other high and better recommendations report, but do not code.  Let moonshot code for you and do not proceed until i approve
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — product architect + HAL systems engineer
for NewRidge Financial 2.0 (NR2), a local HTTPS Apex starship-bridge app for a Kansas dental S-corp.

CRITICAL CONSTRAINTS:
1. Answer ALL parts of the operator request (do not rewrite their wording):
   (A) DESIGN Claims page: rows of 30-day / 60-day / 90-day claims widgets as a LINE OF BOXES.
   (B) Click a claim box → opens the actual claim detail.
   (C) Each claim box shows: Claim ID, Patient Name, Date.
   (D) This widget also has HAL control (board-actions / Ask HAL / focus / sync — never invent $).
   (E) Narratives page must access: clinical notes, claims, insurance information.
   (F) Expand ability for HAL to produce narratives TO INSURANCE COMPANIES.
   (G) Any OTHER high / better recommendations — report them ranked.
2. CONSULT ONLY — DO NOT APPLY / DO NOT CODE until operator explicitly approves.
3. After approval, Moonshot (not Cursor) should implement — state that clearly in the report.
4. Live build reviewed: **hal-10330**. Use LIVE FACTS in the user context as ground truth.
5. Hard rules: never invent financial dollar amounts or claim facts; PHI stays local;
   HAL must not invent claim IDs, patient names, dates, or insurance narrative facts —
   only compose from import-backed SoftDent clinical notes / claims / insurance fields.
6. Preserve Apex mosaic patterns where possible; propose new widget types only when needed
   (e.g. claim-tile-row / claim-detail drawer).
7. Rank MUST / SHOULD / NICE; phased plan with validation gate.
8. Provide paste-ready specs labeled CONSULT ONLY — UI wire description, data contract,
   HAL board-actions, narratives context panel, insurance narrative generation flow.

OUTPUT FORMAT (strict markdown):
# Verdict
## 0. Operator Intent (quote; confirm consult-only; Moonshot codes after approve)
## 1. Claims Page Design — 30 / 60 / 90 Day Tile Rows
Layout, claim box fields (id, patient, date), click → claim detail, empty/honest states.
## 2. HAL Control on Claims Aging Widget
Board-actions, Ask HAL chips, what HAL may / may not do.
## 3. Narratives Page — Clinical Notes + Claims + Insurance Context
How context panel loads import-backed sources; UX for picking a claim/note/payer.
## 4. HAL Insurance-Company Narratives
Expand generate/rewrite to payer appeal / medical necessity / attachment cover letters;
honesty + consent gates.
## 5. Higher / Better Recommendations (beyond the ask)
Ranked MUST / SHOULD / NICE with rationale.
## 6. Moonshot Spec Deliverables (CONSULT ONLY)
Data contracts, widget IDs, API shapes, HAL actions — paste-ready.
## 7. Implementation Phases (C0 validate → Cn) + Validation Gate
State: Moonshot implements after operator approve; Cursor does not code now.
## 8. Risks, PHI / CPA disclaimer & Rollback
DO NOT APPLY until operator says proceed / validated / approve.
"""


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 20),
    ("NewRidgeFinancial2/docs/MOONSHOT_HAL_BOARD_CONTROL_APPLIED_2026-07-10.md", 40),
    ("NewRidgeFinancial2/site/apex-narratives.js", 80),
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

    # Claims widget excerpt from apex_backend
    claims_src = REPO / "NewRidgeFinancial2" / "apex_backend.py"
    if claims_src.is_file():
        text = claims_src.read_text(encoding="utf-8", errors="replace")
        # Pull _claims_summary_from_bundle + _claims_widgets regions by marker
        for marker, label, max_lines in (
            ("def _claims_summary_from_bundle", "_claims_summary_from_bundle", 40),
            ("def _claims_widgets", "_claims_widgets", 80),
            ("def _narratives_widgets", "_narratives_widgets", 60),
            ("def resolve_hal_board_actions", "resolve_hal_board_actions (head)", 50),
        ):
            idx = text.find(marker)
            if idx < 0:
                parts.append(f"### EXCERPT: {label}\n(missing)")
                continue
            chunk = text[idx : idx + 4500]
            parts.append(
                f"### EXCERPT: apex_backend.py::{label}\n```python\n{_truncate(chunk, max_lines)}\n```"
            )

    parts.append(
        """### LIVE FACTS (hal-10330 — captured at consult time)
- Build: hal-10330 (CPA complete pack already applied elsewhere; this consult is NEW scope)
- Claims page TODAY: KPI mosaic only — claims-total, claims-open, claims-denied, claims-aging-30 (single 30+ bucket), claims-follow-up status, claims-velocity-funnel, ins/patient split. NO 30/60/90 tile rows. NO clickable claim boxes. NO claim detail drawer.
- Claims aging logic TODAY: `_claims_summary_from_bundle` only counts Age/Days ≥ 30 into `agingPast30` — no 60/90 bucket split for claim tiles.
- SoftDent claims import typically present (historically ~60 claim rows + claimStatus); Age/Days fields required for aging buckets.
- Claim row fields available when present on SoftDent export: ClaimId / Claim #, Patient / PatientName, Date / DOS / ServiceDate, Status, Age/Days, Payer — never invent missing fields.
- Narratives page TODAY: interactive bridge (`apex-narratives.js`) with section scrubber, composer, HAL Rewrite (clinical style), templates, print packet. Context panel is a placeholder hint — NOT wired to live clinical notes / claims / insurance pickers.
- Narratives backend widgets still expose narr-drafts, narr-clinical-notes count, template library, workflow status — but interactive page does not surface claim/insurance selectors.
- HAL board-actions exist: sync_imports, refresh_page, navigate, focus/highlight widget, categorize assist, import status — never invents $. Ask HAL on mosaic instruments.
- Insurance narrative library exists (`hal_narrative_library`) for generic drafts; operator wants expand to produce narratives TO insurance companies (appeals / medical necessity) from import-backed context + consent.
- Operator: CONSULT ONLY report; do not code; Moonshot codes after approve; Cursor must not proceed until approve.
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
        "CONSULT ONLY — design + recommendations report. Do not apply code.\n"
        "After operator approves, Moonshot (not Cursor) should implement.\n\n"
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
        headers["X-Title"] = "NR2 Claims Narratives Consult"

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
        f"# Moonshot AI — Claims 30/60/90 Tiles + Narratives Insurance HAL (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10330  \n"
        f"**Script:** `scripts/run_moonshot_claims_narratives_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves. Moonshot codes after approve.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_CLAIMS_NARRATIVES_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_CLAIMS_NARRATIVES_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
