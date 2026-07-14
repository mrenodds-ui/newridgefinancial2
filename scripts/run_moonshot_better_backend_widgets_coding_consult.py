"""Moonshot AI — CODING for better backend widgets MUST (then apply path).

Operator: continue with moonshot and do not deviate.
Prior: MOONSHOT_BETTER_BACKEND_WIDGETS_CONSULT_2026-07-12.md
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
continue with moonhot and do not deviate
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — Apex instrumentation engineer for NR2
(build hal-10566). Operator said CONTINUE and DO NOT DEVIATE from your prior
BETTER BACKEND WIDGETS consult.

CRITICAL:
1. Deliver APPLY-READY CODING for the MUST items from
   MOONSHOT_BETTER_BACKEND_WIDGETS_CONSULT_2026-07-12:
   - Tax Planning Data-Table (data-table) on taxes
   - Collections Radial-Gauge (radial-gauge) on financial/ar
   - System Health Status-Matrix (status-matrix) on office-manager/claims
2. DO NOT DEVIATE: keep the MUST intents. If LIVE frontend contracts conflict
   with the consult JSON sketches, ADAPT payloads / minimal FE so the MUST
   intent still ships — document the adaptation clearly. Do not invent a new
   roadmap or swap MUST for unrelated work.
3. LIVE FRONTEND CONTRACTS (must respect or patch minimally):
   - data-table: columns = string[], rows = objects keyed by those column
     strings; emptyMessage; status empty when no rows.
   - radial-gauge: data.due, data.pctScheduled, data.scheduled, data.contacted;
     empty when data.due == null; target marker hard-coded 80% in JS today;
     currently used by W-10 Recall Gauge.
   - status-matrix: data.patients[{hash,elig,ben,breakdown}]; tones
     verified/pending/failed; currently used by W-08 Verification Matrix.
   - action-list: data.items[{label,payer,status,amount,...}]
4. LIVE BACKEND FACTS:
   - Taxes main (_taxes_widgets) already densified (status strips + bridge);
     planning KPIs live on #taxes/planning via packs — emit data-table THERE
     or on main as Moonshot MUST if still additive without re-bloating KPIs.
   - Collection Efficiency already emitted as type bullet (build_collection_bullet).
     MUST wants radial-gauge — either dual-emit collections gauge beside/replacing
     bullet OR generalize radial-gauge FE for collection % WITHOUT breaking W-10.
   - status-matrix already emitted for verification — MUST wants system-health
     matrix. Prefer NEW widget id + FE branch that accepts matrix cells OR map
     SoftDent/QB/Claims/HAL into the existing patients/dot model honestly labeled.
5. Prefer ONE new pack module apex_better_backend_widgets_pack.py + thin wiring
   in apex_backend.py page builders. Minimal apex-core.js patches only if
   required for MUST contracts.
6. Never invent dollars. empty ≠ $0. PLACEHOLDER/null only.
7. Do NOT redo: W-01..W-10 builders, KPI density, zero-scroll, DEF-001, claims pro,
   command strip, horizontal-bar/donut/waterfall already shipped.
8. Operator CONTINUE = coding is for APPLY. Provide paste-ready Python (+ JS if
   needed) and an APPLY ORDER. Mark CONSULT until human applies — but assume
   apply is imminent.

OUTPUT (strict markdown):
# Verdict
## 0. Operator Intent (verbatim continue / do not deviate)
## 1. MUST Adaptations (consult sketch → live contracts)
## 2. Files to Touch
## 3. Paste-ready Code (pack + wiring + any FE patch)
## 4. HAL focus_rules (if any)
## 5. Validation Gate
## 6. Apply Order
## 7. What NOT to redo
"""


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} lines truncated]"


def build_context() -> str:
    parts: list[str] = []
    for rel, max_lines in (
        ("NewRidgeFinancial2/nr2-build.json", 20),
        ("NewRidgeFinancial2/docs/MOONSHOT_BETTER_BACKEND_WIDGETS_CONSULT_2026-07-12.md", 120),
        ("NewRidgeFinancial2/apex_missing_widgets_pack.py", 40),
        ("NewRidgeFinancial2/apex_backend.py", 60),
    ):
        path = REPO / rel
        if not path.is_file():
            parts.append(f"### FILE: {rel}\n(missing)")
            continue
        body = _truncate(path.read_text(encoding="utf-8", errors="replace"), max_lines)
        ext = path.suffix.lstrip(".") or "txt"
        parts.append(f"### FILE: {rel}\n```{ext}\n{body}\n```")

    core = REPO / "NewRidgeFinancial2" / "site" / "apex-core.js"
    if core.is_file():
        js = core.read_text(encoding="utf-8", errors="replace")
        for label, needle, n in (
            ("data-table", 'if (this.type === "data-table")', 45),
            ("status-matrix", 'if (this.type === "status-matrix")', 55),
            ("radial-gauge", 'if (this.type === "radial-gauge")', 60),
            ("action-list", 'if (this.type === "action-list"', 45),
        ):
            i = js.find(needle)
            if i >= 0:
                chunk = "\n".join(js[i:].splitlines()[:n])
                parts.append(f"### LIVE FE: {label}\n```javascript\n{chunk}\n```")

    apex = REPO / "NewRidgeFinancial2" / "apex_backend.py"
    if apex.is_file():
        py = apex.read_text(encoding="utf-8", errors="replace")
        for name in (
            "def build_collection_bullet",
            "def _taxes_widgets",
            "def _ar_widgets",
            "def _office_manager_widgets",
            "def _financial_widgets_from_reports",
        ):
            i = py.find(name)
            if i >= 0:
                parts.append(
                    f"### EXTRACT: {name}\n```python\n"
                    + "\n".join(py[i:].splitlines()[:70])
                    + "\n```"
                )

    pack = REPO / "NewRidgeFinancial2" / "apex_missing_widgets_pack.py"
    if pack.is_file():
        t = pack.read_text(encoding="utf-8", errors="replace")
        for name in ("def build_verification_matrix", "def build_recall_gauge"):
            i = t.find(name)
            if i >= 0:
                parts.append(
                    f"### EXTRACT: {name}\n```python\n"
                    + "\n".join(t[i:].splitlines()[:55])
                    + "\n```"
                )

    # taxes planning subpage tables if any
    sub = REPO / "NewRidgeFinancial2" / "apex_subpages_wave5_pack.py"
    if sub.is_file():
        t = sub.read_text(encoding="utf-8", errors="replace")
        i = t.find("taxes")
        parts.append(
            "### EXTRACT: apex_subpages_wave5_pack (taxes-related start)\n```python\n"
            + _truncate(t[max(0, i - 200) : i + 2500] if i >= 0 else t[:2500], 80)
            + "\n```"
        )

    parts.append(
        """### LIVE FACTS
- Operator CONTINUE + DO NOT DEVIATE from better-backend-widgets MUST list.
- W-08 status-matrix and W-10 radial-gauge already exist with recall/verification semantics.
- Collection bullet already exists — MUST still wants collections radial-gauge.
- Taxes main already KPI-densified — do not re-bloat; data-table for planning is the MUST.
- Prefer pack + wiring; FE patch only if MUST cannot land on live contracts.
- Never invent $. Apply-ready paste code required.
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
        "Continue the better-backend-widgets Moonshot package. DO NOT DEVIATE from "
        "MUST items. Deliver apply-ready coding adapted to LIVE FE contracts.\n\n"
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
        headers["X-Title"] = "NR2 Better Backend Widgets Coding"

    print("Calling Moonshot AI (coding consult — apply after)...")
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
        f"# Moonshot AI — Better Backend Widgets CODING (CONTINUE / NO DEVIATE)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10566  \n"
        f"**Script:** `scripts/run_moonshot_better_backend_widgets_coding_consult.py`  \n"
        f"**Prior:** MOONSHOT_BETTER_BACKEND_WIDGETS_CONSULT_2026-07-12.md  \n"
        f"**Operator:** continue with moonshot — do not deviate  \n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_BETTER_BACKEND_WIDGETS_CODING_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_BETTER_BACKEND_WIDGETS_CODING_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
