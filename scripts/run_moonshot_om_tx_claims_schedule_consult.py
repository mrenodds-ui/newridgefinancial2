"""Moonshot AI — Treatment planning, claims, SoftDent schedule, OM daily appointments.

CONSULT ONLY. Operator request VERBATIM. Await approval before applying code.
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
as expert sofware engineer run through moonshot ai everything about this program for recommendation for treatment planning, claims processing, and handling, and the schedule fro softdent.  Appointments should be loaded into the program everyday of the office manager page. moonshot recommendations with them then report
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — senior NR2 Apex + HAL architect for
NewRidge Family Financial (Kansas dental S-corp; SoftDent + QuickBooks imports;
local Ollama single 24B on R9700; SoftDent READ-ONLY — never write back).

CRITICAL CONSTRAINTS:
1. Answer the OPERATOR REQUEST VERBATIM. Focus ONLY on:
   A) Treatment planning recommendations (program + HAL)
   B) Claims processing and handling
   C) SoftDent schedule / appointments
   D) Explicit operator requirement: Appointments MUST load into the program every day
      on the Office Manager page
2. CONSULT ONLY — DO NOT APPLY code. Wait for approve.
3. Ground EVERY recommendation in LIVE FACTS below. Evolve NR2; no rewrite;
   never invent dollars/PHI; empty ≠ $0; SoftDent read-only.
4. Prefer smallest safe change set. Reuse existing packs/APIs
   (nr2_softdent_daily, softdent_practice_exports, apex_missing_widgets_pack,
   claims/narrative packs, softdent_treatment_planning) before inventing new stacks.
5. Rank MUST / SHOULD / NICE with phases. MUST must include closing the OM daily
   appointments gap if LIVE FACTS show it is broken/missing.
6. End with APPROVAL CHECKLIST (e.g. Approve OM-A0, Approve MUST, Approve all).

OUTPUT FORMAT (strict markdown):
# Verdict — Tx planning / Claims / SoftDent schedule / OM daily appointments
## 0. Operator Intent (quote; consult-only)
## 1. Current State Audit (treatment · claims · schedule · OM) — grounded
## 2. Gap Map
Table: Area | Status | Gap | Effort | Depends on
## 3. Target Design (OM daily appointments + related surfaces)
## 4. Coding Plan by Phase (files to touch · paste-ready sketches · validation)
## 5. MUST / SHOULD / NICE ranked table
## 6. Risks, PHI, SoftDent honesty, Rollback
## 7. Approval Checklist
DO NOT APPLY until operator says approve / proceed.
"""


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} lines truncated]"


def _extract_lines(path: Path, start_marker: str, end_marker: str | None, max_lines: int) -> str:
    if not path.is_file():
        return "(missing)"
    text = path.read_text(encoding="utf-8", errors="replace")
    start = text.find(start_marker)
    if start < 0:
        return f"(marker not found: {start_marker[:80]})"
    if end_marker:
        end = text.find(end_marker, start + len(start_marker))
        chunk = text[start : (end if end > start else start + 14000)]
    else:
        chunk = text[start : start + 14000]
    return _truncate(chunk, max_lines)


CONTEXT_FILES: list[tuple[str, int]] = [
    ("NewRidgeFinancial2/nr2-build.json", 12),
    ("NewRidgeFinancial2/docs/architecture.md", 40),
    ("NewRidgeFinancial2/docs/HAL_LOCAL_24B_SINGLE_GPU_2026-07-11.md", 40),
    ("NewRidgeFinancial2/import-manifest.json", 80),
]


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

    nr2 = REPO / "NewRidgeFinancial2"

    parts.append(
        "### EXTRACT: apex_backend.py — _office_manager_widgets\n```python\n"
        + _extract_lines(nr2 / "apex_backend.py", "def _office_manager_widgets", "def _", 80)
        + "\n```"
    )
    parts.append(
        "### EXTRACT: apex_missing_widgets_pack.py — operatory / treatment / verification\n```python\n"
        + _extract_lines(
            nr2 / "apex_missing_widgets_pack.py",
            "def build_operatory_board",
            "def append_office_manager_missing",
            90,
        )
        + "\n```"
    )
    parts.append(
        "### EXTRACT: nr2_softdent_daily.py — appointments_snapshot\n```python\n"
        + _extract_lines(nr2 / "nr2_softdent_daily.py", "def appointments_snapshot", "def ", 70)
        + "\n```"
    )
    parts.append(
        "### EXTRACT: softdent_practice_exports.py — operatory schedule build\n```python\n"
        + _extract_lines(
            nr2 / "softdent_practice_exports.py",
            "def sync_practice_exports",
            None,
            60,
        )
        + "\n```"
    )
    parts.append(
        "### EXTRACT: softdent_treatment_planning.py — head\n```python\n"
        + _truncate(
            (nr2 / "softdent_treatment_planning.py").read_text(encoding="utf-8", errors="replace")
            if (nr2 / "softdent_treatment_planning.py").is_file()
            else "(missing)",
            50,
        )
        + "\n```"
    )
    parts.append(
        "### EXTRACT: import_loader.py — operatory load markers\n```python\n"
        + _extract_lines(nr2 / "import_loader.py", "_load_operatory", None, 40)
        + "\n```"
    )

    app_js = nr2 / "site" / "app.js"
    if app_js.is_file():
        text = app_js.read_text(encoding="utf-8", errors="replace")
        hits = []
        for needle in (
            'page.id === "softdent"',
            "appointments-snapshot",
            "office-manager",
            "NR2SoftdentDaily",
        ):
            i = text.find(needle)
            if i >= 0:
                start = max(0, text.rfind("\n", 0, i) - 200)
                hits.append(text[start : start + 500])
        parts.append(
            "### EXTRACT: site/app.js — SoftDent vs OM live prefetch snippets\n```javascript\n"
            + _truncate("\n---\n".join(hits) if hits else "(no hits)", 80)
            + "\n```"
        )

    parts.append(
        """### LIVE FACTS (operator consult — treatment / claims / schedule / OM)
- Local AI: single `hal-local:24b` on R9700; SoftDent read-only; no SoftDent write-back.
- Program Manager upgrade waves complete; this is a NEW scoped consult (not PM re-audit).
- Office Manager page: `#office-manager` (+ huddle/tasks). Widgets include daily huddle,
  operatory util board, treatment pipeline, verification matrix, claims-related HAL-said widgets.
- SoftDent schedule today:
  - Bundle key `operatory` from `operatory_schedule.json` / chairs JSON via import_loader.
  - Generated by `softdent_practice_exports.sync_practice_exports` from Sensei/`sd_appointments`
    during import sync — NOT a first-class `softdent.appointments` manifest dataset.
  - Live `/api/softdent/appointments-snapshot` + operatory-grid exist in `nr2_softdent_daily.py`.
  - Browser live prefetch currently runs when SoftDent page opens — NOT when Office Manager opens.
- OM widgets (`build_operatory_board`, verification matrix) look for keys like `schedule_today`,
  `appointments_next_3d`, `softdent.appointments` / `softdent.schedule` that the loader often
  NEVER populates → boards stay empty without operatoryChairs fallback path.
- Claims: Claims workbench + narratives packs + HAL tools (read_claims_summary, join_claim_payers,
  draft_insurance_narrative, ERA tools, etc.). OM has verification matrix / follow-up hints, not full workbench.
- Treatment planning: `softdent.treatmentPlans` + caseAcceptance imports; OM treatment pipeline widget;
  `softdent_treatment_planning.py` estimate ingest/lookup (not always a first-class HAL tool name).
- Operator MUST: Appointments loaded into the program every day on the Office Manager page.
- Prefer wire OM page-open → appointments snapshot refresh + populate OM widgets from existing
  APIs over inventing a second SoftDent live integration.
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
        "CONSULT ONLY — recommend treatment planning, claims processing/handling, "
        "SoftDent schedule, and daily OM appointments loading. Do not apply.\n\n"
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
        headers["X-Title"] = "NR2 OM Schedule Tx Claims Consult"

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
        f"# Moonshot AI — Treatment / Claims / SoftDent Schedule / OM Appointments (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Script:** `scripts/run_moonshot_om_tx_claims_schedule_consult.py`  \n"
        f"**Apply:** DO NOT APPLY / DO NOT CODE until operator approves.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_OM_TX_CLAIMS_SCHEDULE_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_OM_TX_CLAIMS_SCHEDULE_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
