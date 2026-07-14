"""Moonshot AI — CODING for better backend widgets SHOULD wave.

Operator: continue (after MUST applied as hal-10567).
Prior: MOONSHOT_BETTER_BACKEND_WIDGETS_CONSULT + CODING + APPLIED.
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

OPERATOR_REQUEST_VERBATIM = "continue"

SYSTEM = """You are Moonshot AI (kimi-k2 class) — Apex instrumentation engineer for NR2
(build **hal-10567**). Operator said CONTINUE after MUST Better Backend Widgets shipped.

CRITICAL:
1. Deliver APPLY-READY CODING for the SHOULD items ONLY from
   MOONSHOT_BETTER_BACKEND_WIDGETS_CONSULT_2026-07-12:
   - HAL Action-List (action-list) on hal + office-manager
   - A/R Collection Task-List (collection-task-list) on ar
   - AI Insight Card (ai-insight) on narratives (+ hal if gap)
   - Patient Dossier Card (patient-dossier-card) on softdent
2. DO NOT DEVIATE into NICE (pareto, tax-calendar, timeline-lanes) or redo MUST.
3. LIVE FACTS — do not duplicate what already ships; FILL GAPS:
   - action-list already used (claims needing narrative, treatment plans, etc.)
   - patient-dossier-card already on office-manager via apex_missing_widgets_pack
   - ai-insight already on HAL via apex_structured_insight_pack.ai_insight_widget
   - collection-task-list already on A/R collections SUBPAGE via apex_subpages_pack
   SHOULD gaps to close if still missing on TARGET pages:
   - SoftDent page needs patient-dossier-card (empty until patient selected)
   - A/R MAIN page needs collection-task-list (seeds from aging/denied; honest empty)
   - Narratives page needs ai-insight (rule-backed variance; no invented $)
   - HAL / OM need a focused recommended-actions action-list if not already
     present as Moonshot SHOULD intent (prefer new widget ids; do not break
     existing builders)
4. LIVE FE CONTRACTS (must match; FE patch only if unavoidable):
   - action-list: data.items[{label|id, payer, status, amount, serviceDate}]
   - collection-task-list: seeds[{claimId, patientInitials, ageDays, bucket,
     billedAmount}], notes[], status empty only when no seeds AND no notes
   - ai-insight: insight{widget_type, confidence, explanation, source_refs,
     data, action_cta}; widget_type in kpi-card|trend-chart|alert-banner
   - patient-dossier-card: data{patientHash, initials, primaryCarrier,
     openClaims, lastVisit, accountBalance, hasClinicalNotes, emptyMessage}
5. Prefer extending apex_better_backend_widgets_pack.py + thin apex_backend.py
   wiring. Reuse existing packs when a one-line call closes the gap.
6. Never invent dollars/claim IDs/patients. PHI = initials/hash only.
7. Operator CONTINUE = apply-ready paste code + Apply Order.

OUTPUT (strict markdown):
# Verdict
## 0. Operator Intent
## 1. Gap vs Already-Shipped (per SHOULD)
## 2. Files to Touch
## 3. Paste-ready Code
## 4. Validation Gate
## 5. Apply Order
## 6. What NOT to redo
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
        ("NewRidgeFinancial2/docs/MOONSHOT_BETTER_BACKEND_WIDGETS_APPLIED_2026-07-12.md", 60),
        ("NewRidgeFinancial2/docs/MOONSHOT_BETTER_BACKEND_WIDGETS_CONSULT_2026-07-12.md", 55),
        ("NewRidgeFinancial2/apex_better_backend_widgets_pack.py", 40),
    ):
        path = REPO / rel
        if path.is_file():
            body = _truncate(path.read_text(encoding="utf-8", errors="replace"), max_lines)
            ext = path.suffix.lstrip(".") or "txt"
            parts.append(f"### FILE: {rel}\n```{ext}\n{body}\n```")

    # Existing builders
    for rel, needles in (
        (
            "NewRidgeFinancial2/apex_missing_widgets_pack.py",
            (
                "def build_claims_needing_narrative",
                "def build_patient_dossier_card",
                "def append_ar_missing",
                "def append_office_manager_missing",
            ),
        ),
        (
            "NewRidgeFinancial2/apex_structured_insight_pack.py",
            ("def ai_insight_widget",),
        ),
        (
            "NewRidgeFinancial2/apex_subpages_pack.py",
            ("def build_collections_workbench", "collection-task-list"),
        ),
    ):
        path = REPO / rel
        if not path.is_file():
            continue
        t = path.read_text(encoding="utf-8", errors="replace")
        for n in needles:
            i = t.find(n)
            if i >= 0:
                parts.append(
                    f"### EXTRACT: {rel} :: {n}\n```python\n"
                    + "\n".join(t[i:].splitlines()[:50])
                    + "\n```"
                )

    apex = REPO / "NewRidgeFinancial2" / "apex_backend.py"
    if apex.is_file():
        py = apex.read_text(encoding="utf-8", errors="replace")
        for name in (
            "def _ar_widgets",
            "def _softdent_widgets",
            "def _narratives_widgets",
            "def _hal_widgets",
            "def _office_manager_widgets",
        ):
            i = py.find(name)
            if i >= 0:
                parts.append(
                    f"### EXTRACT: {name}\n```python\n"
                    + "\n".join(py[i:].splitlines()[:55])
                    + "\n```"
                )

    parts.append(
        """### LIVE FACTS
- MUST shipped as hal-10567 (tax table, collections gauge, system health).
- Operator CONTINUE → SHOULD wave only.
- Prefer gap-fill on target pages over reinventing existing widgets.
- Never invent $. Apply-ready code required.
"""
    )
    return "\n\n".join(parts)


def main() -> int:
    key_name, api_key, base_url = resolve_api_and_endpoint()
    if not api_key:
        print("No API key", file=sys.stderr)
        return 1
    if "moonshot" in (base_url or "").lower():
        model = str(os.getenv("MOONSHOT_MODEL") or "kimi-k2.5").strip()
    else:
        model = str(
            os.getenv("MOONSHOT_MODEL") or os.getenv("KIMI_K2_MODEL") or "moonshotai/kimi-k2"
        ).strip()
    print(f"Using {key_name} @ {base_url} model={model}")
    user = (
        "OPERATOR REQUEST (VERBATIM):\n\n"
        f"{OPERATOR_REQUEST_VERBATIM}\n\n"
        "Continue Moonshot better-backend-widgets with SHOULD wave only. "
        "Apply-ready coding. Do not redo MUST. Do not start NICE.\n\n"
        "## Context\n\n" + build_context()
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
        headers["X-Title"] = "NR2 Better Backend Widgets SHOULD"
    print("Calling Moonshot AI (SHOULD coding)...")
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
        f"# Moonshot AI — Better Backend Widgets SHOULD CODING\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build base:** hal-10567  \n"
        f"**Script:** `scripts/run_moonshot_better_backend_widgets_should_coding.py`  \n"
        f"**Operator:** continue (SHOULD wave)  \n\n"
        f"## Operator request (verbatim)\n\n> {OPERATOR_REQUEST_VERBATIM}\n\n---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_BETTER_BACKEND_WIDGETS_SHOULD_CODING_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_BETTER_BACKEND_WIDGETS_SHOULD_CODING_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
