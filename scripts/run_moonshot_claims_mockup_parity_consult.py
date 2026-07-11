"""Moonshot AI — Can Apex Claims page function/look like 2026-07-07 page_mockups/claims.html?

CONSULT ONLY. Do not apply code. Await operator approval.
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

MOCKUP = (
    REPO
    / "_archive"
    / "2026-07-10"
    / ".local_logs"
    / "moonshot_financial_eval"
    / "page_mockups"
    / "claims.html"
)

OPERATOR_REQUEST_VERBATIM = """
ask moonshot ai if he can make the claims page function like the attached html and look like the claims in there can be presented that way? then report
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — product architect + HAL systems engineer
for NewRidge Financial 2.0 (NR2), a local HTTPS Apex starship-bridge app for a Kansas dental S-corp.

CRITICAL CONSTRAINTS:
1. Answer the operator request VERBATIM: Can the live Apex Claims page FUNCTION like
   `_archive/.../page_mockups/claims.html` AND can claims be PRESENTED that way (look)?
2. CONSULT ONLY — DO NOT APPLY / DO NOT CODE until operator explicitly approves.
3. Use LIVE FACTS + attached HTML as ground truth. Never invent claim IDs, patients,
   dollar amounts, ERA match %, or denial codes as real practice data.
4. Be honest about gaps: SoftDent import fields vs mockup fields (risk, attachments,
   ERA match, CDT procedure, drag-status columns).
5. Distinguish: (A) visual presentation parity, (B) functional behavior parity,
   (C) what is already shipped (30/60/90 claim-shelf), (D) what needs new data/APIs.
6. Rank MUST / SHOULD / NICE. Phased plan. Validation gate.
7. Preserve Apex shell (do not resurrect full mockup sidebar as the app chrome unless
   operator wants a full Claims Workbench page mode). Prefer Apex mosaic + widgets
   unless a dedicated claims workbench page is clearly better — say which and why.

OUTPUT FORMAT (strict markdown):
# Verdict
## 0. Operator Intent (quote; confirm consult-only)
## 1. What the 2026-07-07 claims.html Mockup Is
Layout, kanban columns, claim-card fields, side widgets, interactions.
## 2. Feasibility — Look (presentation)
Can Apex present claims as those cards / columns? What CSS/widget work?
## 3. Feasibility — Function (behavior)
Filters, drag-status, ERA match, risk badges, attachment checklist, click→detail —
what works today vs needs SoftDent/ERA data vs must stay honest-empty.
## 4. Gap Matrix (Mockup feature → Live capability → Blocker)
Table.
## 5. Recommended Approach
Adopt / adapt / hybrid with existing 30/60/90 shelves — ranked options.
## 6. Moonshot Spec (CONSULT ONLY)
Widget IDs, data contract, HAL actions — paste-ready.
## 7. Phases + Validation Gate
State: Moonshot implements after approve; Cursor does not code now.
## 8. Risks, PHI / honesty & Rollback
DO NOT APPLY until operator says proceed / approve.
"""


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} lines truncated]"


def _mockup_excerpt() -> str:
    if not MOCKUP.is_file():
        return "(missing claims.html mockup)"
    text = MOCKUP.read_text(encoding="utf-8", errors="replace")
    # Prefer body structure over full CSS for token budget
    body_idx = text.lower().find("<body")
    if body_idx < 0:
        return _truncate(text, 220)
    head = text[: min(body_idx, 800)]
    body = text[body_idx:]
    # Drop long script if present at end
    script_idx = body.lower().rfind("<script")
    if script_idx > 0:
        body = body[:script_idx] + "\n<!-- script truncated -->\n</body></html>"
    return _truncate(head + "\n...\n" + body, 420)


def build_context() -> str:
    parts: list[str] = []
    parts.append(
        "### ATTACHED MOCKUP (operator reference)\n"
        f"Path: `{MOCKUP.relative_to(REPO).as_posix()}`\n"
        "```html\n"
        + _mockup_excerpt()
        + "\n```"
    )

    for rel, max_lines in (
        ("NewRidgeFinancial2/nr2-build.json", 20),
        ("NewRidgeFinancial2/docs/MOONSHOT_CLAIMS_NARRATIVES_APPLIED_2026-07-10.md", 80),
        ("NewRidgeFinancial2/apex_claims_narratives_pack.py", 100),
    ):
        path = REPO / rel
        if not path.is_file():
            parts.append(f"### FILE: {rel}\n(missing)")
            continue
        body = _truncate(path.read_text(encoding="utf-8", errors="replace"), max_lines)
        ext = path.suffix.lstrip(".") or "txt"
        parts.append(f"### FILE: {rel}\n```{ext}\n{body}\n```")

    claims_src = REPO / "NewRidgeFinancial2" / "apex_backend.py"
    if claims_src.is_file():
        text = claims_src.read_text(encoding="utf-8", errors="replace")
        for marker, label, max_lines in (
            ("def _claims_summary_from_bundle", "_claims_summary_from_bundle", 50),
            ("def _claims_widgets", "_claims_widgets", 80),
        ):
            idx = text.find(marker)
            if idx < 0:
                parts.append(f"### EXCERPT: {label}\n(missing)")
                continue
            chunk = text[idx : idx + 5000]
            parts.append(
                f"### EXCERPT: apex_backend.py::{label}\n```python\n{_truncate(chunk, max_lines)}\n```"
            )

    parts.append(
        """### LIVE FACTS (hal-10370 — consult time)
- Build: hal-10370 Apex epoch.
- Claims page TODAY: mosaic + claim-shelf widgets for 30/60/90 aging (hal-10360 pack).
  Click tile → claim detail drawer; Draft Narrative seed; bulk select/appeal; HAL focus/Ask HAL.
- NOT today: 5-column status kanban (Submitted / Pending Review / ERA Matched / Denied / Paid),
  drag-to-update status, denial-risk badges as scored risk, attachment completeness chips,
  ERA match list widget, header Pending $ / At Risk / ERA Match % as live inventable KPIs.
- SoftDent claim rows when imported may include ClaimId, Patient, Date/DOS, Status, Age/Days,
  Payer — procedure/CDT, attachment counts, ERA match, denial CARC/RARC, and dollar amounts
  only when present on import; NEVER invent.
- Mockup HTML is a static demo with fictional CT practice branding, fake claim IDs, and
  invented dollars — presentation target only, not data source.
- Operator wants: FUNCTION like the HTML + PRESENT claims that way → report feasibility.
- CONSULT ONLY; Moonshot codes after approve; Cursor must not implement now.
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
        "CONSULT ONLY — feasibility + recommendations report. Do not apply code.\n"
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
        headers["X-Title"] = "NR2 Claims Mockup Parity Consult"

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
        f"# Moonshot AI — Claims Mockup Parity vs page_mockups/claims.html (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10370  \n"
        f"**Mockup:** `_archive/2026-07-10/.local_logs/moonshot_financial_eval/page_mockups/claims.html`  \n"
        f"**Script:** `scripts/run_moonshot_claims_mockup_parity_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator approves. Moonshot codes after approve.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_CLAIMS_MOCKUP_PARITY_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_CLAIMS_MOCKUP_PARITY_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
