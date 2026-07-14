"""Moonshot AI — Better widgets usable from the backend (CONSULT ONLY).

Operator request is passed VERBATIM. Do not rewrite operator intent.
Does NOT apply any code.
"""

from __future__ import annotations

import json
import os
import re
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
ask moonshot ai if there are better widgets that can be used from the backend then report
""".strip()

SYSTEM = """You are Moonshot AI (kimi-k2 class) — Apex instrumentation architect for
NewRidge Financial 2.0 (NR2), a local HTTPS Bottle starship-bridge app
(SoftDent + QuickBooks imports, local HAL). Build under review: **hal-10566**.

CRITICAL:
1. Answer the operator VERBATIM: are there BETTER widgets that can be used FROM THE
   BACKEND (apex_backend.py / page packs emitting mosaic JSON)? Then REPORT.
2. CONSULT ONLY — DO NOT APPLY / DO NOT CODE into the live repo until operator approves.
3. Focus on BACKEND-EMITTING instruments: JSON specs the Python backend can already
   (or should) emit into /api/apex/widgets/<page>. Prefer types apex-core.js already
   renders over inventing brand-new frontend work.
4. Never invent dollar amounts, claim IDs, patients, ERA %, or clinical facts.
   Payloads use null/empty or PLACEHOLDER structure only.
5. Hard rules: SoftDent/QB import-backed honesty; empty ≠ $0; no third-party embeds
   (TradingView, bank OAuth, etc.); wipe-safe native Apex only.
6. Distinguish three buckets clearly:
   A) Frontend-already-renders but backend underuses (quick wins — emit more)
   B) Better instrument CHOICES for existing pages (replace weak KPI spam with denser types)
   C) New backend builders that need modest new JS (only if A/B insufficient)
7. Rank MUST / SHOULD / NICE by practice-ops ROI vs effort. Map to real pages:
   financial, taxes, softdent, quickbooks, ar, claims, narratives, documents,
   library, office-manager, hal.
8. Account for JUST SHIPPED / already applied so you do not re-propose them as new:
   horizontal-bar, donut, stacked-bar, bullet, waterfall, scrubber, KPI density,
   zero-scroll, W-01..W-10 missing widgets, claims pro, financial command strip,
   DEF-001 / Register XLS honesty, cache coherence, Phase 5 190Q.
9. Prefer densifying UNDERUSED renderer types over adding more bare kpi widgets.

OUTPUT FORMAT (strict markdown):
# Verdict (one sentence)
## 0. Operator Intent (quote; confirm consult-only)
## 1. Gap Analysis (backend emits vs frontend can render)
## 2. Better Backend Widgets — Ranked
Table: name | type id | page(s) | data source | vs current | MUST/SHOULD/NICE | effort
## 3. Quick Wins (frontend ready — backend emit only)
## 4. Better Choices (replace/upgrade weak existing widgets)
## 5. Per-Page Backend Placement Map
## 6. Spec Sketches (JSON shapes, CONSULT ONLY — no invented dollars)
## 7. What NOT to redo
## 8. Approval Checklist
DO NOT APPLY until operator says approve / proceed.
"""


def _truncate(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} lines truncated]"


def _extract_frontend_types(js: str) -> list[str]:
    found = sorted(set(re.findall(r'this\.type === "([^"]+)"', js)))
    return found


def _extract_backend_types(py: str) -> list[str]:
    # widget payload types (exclude HAL action types)
    skips = {
        "navigate",
        "focus_widget",
        "highlight_widget",
        "refresh_page",
        "refresh_widget",
        "sync_imports",
        "set_status_banner",
        "set_inputs",
        "save_scenario",
        "narrative_append",
        "run_tool",
        "focus_claim_tile",
        "open_claim_detail",
        "refresh_softdent_period",
        "system",
        "metric",
        "alert",
        "hal",
    }
    found = sorted(
        {
            t
            for t in re.findall(r'"type":\s*"([^"]+)"', py)
            if t not in skips and not t.startswith("set_")
        }
    )
    return found


def build_context() -> str:
    parts: list[str] = []
    build = REPO / "NewRidgeFinancial2" / "nr2-build.json"
    if build.is_file():
        parts.append(
            "### FILE: NewRidgeFinancial2/nr2-build.json\n```json\n"
            + build.read_text(encoding="utf-8", errors="replace")
            + "\n```"
        )

    apex = REPO / "NewRidgeFinancial2" / "apex_backend.py"
    core = REPO / "NewRidgeFinancial2" / "site" / "apex-core.js"
    be_types: list[str] = []
    fe_types: list[str] = []
    if apex.is_file():
        py = apex.read_text(encoding="utf-8", errors="replace")
        be_types = _extract_backend_types(py)
        # builders header
        builders = [
            ln.strip()
            for ln in py.splitlines()
            if ln.startswith("def build_") or ln.startswith("def _") and "_widgets" in ln
        ][:80]
        parts.append(
            "### EXTRACT: apex_backend builders / page widget fns\n```\n"
            + "\n".join(builders)
            + "\n```"
        )
        parts.append(
            "### EXTRACT: backend widget type strings seen in apex_backend.py\n```\n"
            + ", ".join(be_types)
            + "\n```"
        )
        # financial widgets section
        i = py.find("def _financial_widgets_from_reports")
        if i >= 0:
            parts.append(
                "### EXTRACT: _financial_widgets_from_reports (start)\n```python\n"
                + py[i : i + 3500]
                + "\n```"
            )

    if core.is_file():
        js = core.read_text(encoding="utf-8", errors="replace")
        fe_types = _extract_frontend_types(js)
        parts.append(
            "### EXTRACT: apex-core.js this.type === branches\n```\n"
            + ", ".join(fe_types)
            + "\n```"
        )
        # size map
        j = js.find("function widgetSize")
        if j < 0:
            j = js.find("widgetSize")
        if j >= 0:
            parts.append(
                "### EXTRACT: apex-core size map (approx)\n```javascript\n"
                + js[j : j + 2200]
                + "\n```"
            )

    underused = sorted(set(fe_types) - set(be_types))
    parts.append(
        "### DERIVED GAP (frontend type branches not clearly emitted by apex_backend.py)\n```\n"
        + (", ".join(underused) if underused else "(none detected)")
        + "\n```"
    )

    for rel, max_lines in (
        ("NewRidgeFinancial2/docs/MOONSHOT_MORE_WIDGETS_FLASH_CONSULT_2026-07-10.md", 60),
        ("NewRidgeFinancial2/docs/MOONSHOT_MISSING_WIDGETS_LOOK_CONSULT_2026-07-11.md", 80),
        ("NewRidgeFinancial2/docs/MOONSHOT_KPI_DENSITY_FIX_CONSULT_2026-07-12.md", 40),
    ):
        path = REPO / rel
        if path.is_file():
            body = _truncate(path.read_text(encoding="utf-8", errors="replace"), max_lines)
            parts.append(f"### FILE: {rel}\n```md\n{body}\n```")
        else:
            parts.append(f"### FILE: {rel}\n(missing)")

    parts.append(
        """### LIVE FACTS (hal-10566)
- Backend: apex_backend.py emits mosaic widgets per page via build_apex_widgets.
- Frontend: apex-core.js Widget class switches on spec.type — many types already render.
- Operator asks: are there BETTER widgets that can be used FROM THE BACKEND? REPORT only.
- Do not propose redoing KPI density, zero-scroll, W-01..W-10, DEF-001 honesty, Register XLS.
- Prefer emitting underused frontend-ready types over inventing new chart libraries.
- Never invent dollars; honest empty states.
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
        "CONSULT ONLY — report whether better backend-usable widgets exist. Do not apply.\n\n"
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
        headers["X-Title"] = "NR2 Better Backend Widgets Consult"

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
        f"# Moonshot AI — Better Backend Widgets (CONSULT ONLY)\n\n"
        f"**Date:** {DATE}  \n"
        f"**Model:** {model}  \n"
        f"**Key:** {key_name}  \n"
        f"**Endpoint:** {base_url}  \n"
        f"**Status:** {status}  \n"
        f"**Build reviewed:** hal-10566  \n"
        f"**Script:** `scripts/run_moonshot_better_backend_widgets_consult.py`  \n"
        f"**Apply:** DO NOT APPLY until operator validates.\n\n"
        f"## Operator request (verbatim)\n\n"
        f"> {OPERATOR_REQUEST_VERBATIM}\n\n"
        f"---\n\n"
    )
    full = header + (content or "(empty)")
    out_file = OUT / f"MOONSHOT_BETTER_BACKEND_WIDGETS_CONSULT_{DATE}.md"
    doc_file = DOCS / f"MOONSHOT_BETTER_BACKEND_WIDGETS_CONSULT_{DATE}.md"
    out_file.write_text(full, encoding="utf-8")
    doc_file.write_text(full, encoding="utf-8")
    print(out_file)
    print(doc_file)
    print(f"chars={len(content or '')} status={status}")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
