"""Moonshot AI — Why HAL says Collections empty on HAL inventory + fix with code.

CONSULT ONLY. Operator request VERBATIM. Await approval before applying.
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
ask moonshot ai why hal says this and how to fix and code - age `hal` inventory: 8 with data, 1 empty (of 9). Showing: Ask HAL, Import Health, Program Posture, HAL Suggestion, Production, A/R, Claims, Local Categorize Assist Empty: Collections (Collections pending/missing.)
07:16 AM
Copy
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — SoftDent import honesty + HAL board
architect for NewRidge Financial 2.0 Apex (local HTTPS).

CRITICAL:
1. Answer VERBATIM: WHY HAL said that inventory message, HOW TO FIX (ops + code),
   and provide paste-ready CODE. CONSULT ONLY — do not apply until operator approves.
2. Ground in the codebase context. Do NOT invent dollar amounts or claim collections exist.
3. The message is from format_page_inventory_reply / widget census on page `hal`,
   NOT from the LLM. Empty Collections = hal-mosaic-coll KPI with value null because
   latest SoftDent period has collectionsPending / collectionsReported false / no collections.
4. Distinguish: (A) operational fix (import daysheet / Register for a Period / Sync /
   SoftDent period refresh) vs (B) product/code fix (clearer pending status, HAL reply
   with actionable board-actions, optionally surface prior-period collections with honesty).
5. Prefer honesty: never display $0 as collections when pending. Prefer status=pending
   messaging over fake zeros.
6. Provide paste-ready Python/JS deltas labeled CONSULT ONLY.
7. End with APPROVAL CHECKLIST — STOP until approve/proceed.

OUTPUT FORMAT (strict markdown):
# Verdict — Why HAL said this (one paragraph)
## 0. Operator Intent
## 1. Causal Chain (query → board-actions → census → Collections empty)
## 2. Root Cause in SoftDent period merge (collectionsPending rules)
## 3. Operational Fix (staff steps — no invented $)
## 4. Code Fix Options (ranked) + Recommended path
## 5. Paste-Ready Code (CONSULT ONLY)
## 6. Files to Touch + Validation Gates
## 7. Approval Checklist
DO NOT APPLY until operator says approve / proceed.
"""


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} lines truncated]"


def _extract(path: Path, start: str, end: str | None, max_lines: int) -> str:
    if not path.is_file():
        return "(missing)"
    text = path.read_text(encoding="utf-8", errors="replace")
    i = text.find(start)
    if i < 0:
        return f"(marker not found: {start[:80]})"
    if end:
        j = text.find(end, i + len(start))
        chunk = text[i : (j if j > i else i + 8000)]
    else:
        chunk = text[i : i + 8000]
    return _truncate(chunk, max_lines)


def build_context() -> str:
    apex = REPO / "NewRidgeFinancial2" / "apex_backend.py"
    sync = REPO / "NewRidgeFinancial2" / "softdent_dashboard_period_sync.py"
    parts = []
    parts.append(
        "### EXTRACT: _hal_widgets Collections KPI\n```python\n"
        + _extract(apex, 'widgets.append(\n        _money_kpi(\n            "hal-mosaic-coll"', "ar = reports.get", 40)
        + "\n```"
    )
    parts.append(
        "### EXTRACT: format_page_inventory_reply\n```python\n"
        + _extract(apex, "def format_page_inventory_reply", "def build_export_playbook", 40)
        + "\n```"
    )
    parts.append(
        "### EXTRACT: board-actions census branch\n```python\n"
        + _extract(
            apex,
            "# --- Widget data census (current page, named page, or all pages) ---",
            "# --- What should HAL learn",
            120,
        )
        + "\n```"
    )
    parts.append(
        "### EXTRACT: softdent _build_period_row collectionsPending\n```python\n"
        + _extract(sync, "def _build_period_row", "def _month_rows", 80)
        + "\n```"
    )
    parts.append(
        "### EXTRACT: _include_collections_from_source\n```python\n"
        + _extract(sync, "def _include_collections_from_source", "def _prior_source_dict", 40)
        + "\n```"
    )
    parts.append(
        "### EXTRACT: SoftDent page Collections KPI hint\n```python\n"
        + _extract(apex, '"sd-collections"', "np_rows = _section_rows", 35)
        + "\n```"
    )
    parts.append(
        """### LIVE FACTS
- HAL reply text matches format_page_inventory_reply exactly (inventory: N with data, M empty).
- Ask HAL is excluded from census (hal-chat skipped) but still listed in "Showing" via
  populatedWidgets using non-chat widgets only — wait: inventory lists Ask HAL in Showing?
  Looking at format_page_inventory_reply: populated from census; summarize_widget_census
  SKIPS wid.startswith("hal-chat"). So "Ask HAL" in Showing means either another widget
  labeled Ask HAL OR census changed. Operator message lists Ask HAL in Showing —
  check: widget id "hal-ask" type hal-chat is skipped; unless label appears elsewhere.
  Actually operator message: "Showing: Ask HAL, Import Health,..." — if hal-chat is
  skipped, Ask HAL shouldn't appear. Possible: _widget_has_data treats chat as data OR
  skip rule only skips id startswith "hal-chat" but id is "hal-ask". THAT IS A BUG TO NOTE:
  skip is wid.startswith("hal-chat") but widget id is "hal-ask" type "hal-chat" — so Ask HAL
  is counted as with-data! Mention in consult.
- Empty Collections hint: "Collections pending/missing." from _hal_widgets when coll is None.
- Production shows data → SoftDent period has production; collections intentionally withheld
  when collectionsPending (honesty: not $0).
- Operator wants WHY + HOW TO FIX + CODE. CONSULT ONLY until approve.
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
        "Explain why HAL said that, how to fix (ops + code), paste-ready code. "
        "CONSULT ONLY — wait for approval.\n\n"
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
        headers["X-Title"] = "NR2 HAL Collections Empty Inventory Consult"

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
        f"# Moonshot AI — HAL Collections Empty Inventory (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Script:** `scripts/run_moonshot_hal_collections_empty_consult.py`  \n"
        f"**Apply:** DO NOT APPLY / WAIT FOR OPERATOR APPROVAL.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_HAL_COLLECTIONS_EMPTY_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_HAL_COLLECTIONS_EMPTY_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
