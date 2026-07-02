"""Run one isolated 235B audit section on evaluator lane :11436 only."""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVALUATOR_URL = "http://127.0.0.1:11436"
FRONTEND_URL = "http://127.0.0.1:11434"
BACKEND_URL = "http://127.0.0.1:11435"
MODEL = "qwen3:235b"
MAX_CONTEXT_CHARS = 22_000
MICRO_CONTEXT_CHARS = 12_000
SLICE_CONTEXT_CHARS = 12_000
TIMEOUT_SECONDS = 3600
MICRO_SECTIONS = frozenset({"1a", "1b", "1c", "2a", "2b", "2c"})
SLICE_SECTIONS = frozenset(
    {
        "1a1",
        "1a2",
        "1b1",
        "1b2",
        "1c1",
        "1c2",
        "2a1",
        "2a2",
        "2b1",
        "2b2",
        "2c1",
        "2c2",
    }
)
COMPACT_SECTIONS = MICRO_SECTIONS | SLICE_SECTIONS


def context_limit_for(key: str) -> int:
    if key in SLICE_SECTIONS:
        return SLICE_CONTEXT_CHARS
    if key in MICRO_SECTIONS:
        return MICRO_CONTEXT_CHARS
    return MAX_CONTEXT_CHARS

SECTION_META: dict[str, dict[str, str | Path | None]] = {
    "1": {
        "title": "Section 1 — Backend data/import/widget pipeline",
        "report": "235b_section1_backend_pipeline_report.md",
        "focus": ROOT / "235b_eval_section1_focus.txt",
        "fallback": ROOT / "235b_eval_section1_backend.txt",
    },
    "2": {
        "title": "Section 2 — Frontend dashboard/widget rendering",
        "report": "235b_section2_frontend_dashboard_report.md",
        "focus": ROOT / "235b_eval_section2_focus.txt",
        "fallback": ROOT / "235b_eval_section2_frontend.txt",
    },
    "3": {
        "title": "Section 3 — Local AI lane routing and runtime scripts",
        "report": "235b_section3_ai_routing_report.md",
        "focus": ROOT / "235b_eval_section3_ai_routing.txt",
        "fallback": None,
    },
    "4": {
        "title": "Section 4 — Security/auth/config",
        "report": "235b_section4_security_config_report.md",
        "focus": ROOT / "235b_eval_section4_security.txt",
        "fallback": None,
    },
    "5": {
        "title": "Section 5 — Tests/docs consistency",
        "report": "235b_section5_tests_docs_report.md",
        "focus": ROOT / "235b_eval_section5_tests.txt",
        "fallback": None,
    },
    "1a": {
        "title": "Section 1A — SoftDent period sync and collections pipeline",
        "report": "235b_section1a_softdent_period_report.md",
        "focus": ROOT / "235b_eval_section1a_focus.txt",
        "fallback": None,
    },
    "1b": {
        "title": "Section 1B — Import loader comparable periods and accounting",
        "report": "235b_section1b_import_loader_report.md",
        "focus": ROOT / "235b_eval_section1b_focus.txt",
        "fallback": None,
    },
    "1c": {
        "title": "Section 1C — Python import loader and practice source access",
        "report": "235b_section1c_import_pipeline_report.md",
        "focus": ROOT / "235b_eval_section1c_focus.txt",
        "fallback": None,
    },
    "2a": {
        "title": "Section 2A — HAL skills and widget contract validation",
        "report": "235b_section2a_widget_contract_report.md",
        "focus": ROOT / "235b_eval_section2a_focus.txt",
        "fallback": None,
    },
    "2b": {
        "title": "Section 2B — Practice financial overview and master chart",
        "report": "235b_section2b_financial_overview_report.md",
        "focus": ROOT / "235b_eval_section2b_focus.txt",
        "fallback": None,
    },
    "2c": {
        "title": "Section 2C — Page canvas and HAL page validation",
        "report": "235b_section2c_page_canvas_report.md",
        "focus": ROOT / "235b_eval_section2c_focus.txt",
        "fallback": None,
    },
    "1a1": {
        "title": "Slice 1A1 — SoftDent period row / collections flags",
        "report": "235b_section1a1_softdent_sync_core_report.md",
        "focus": ROOT / "235b_eval_section1a1_focus.txt",
        "fallback": None,
    },
    "1a2": {
        "title": "Slice 1A2 — Direct import pipeline + period sync tests",
        "report": "235b_section1a2_direct_pipeline_report.md",
        "focus": ROOT / "235b_eval_section1a2_focus.txt",
        "fallback": None,
    },
    "1b1": {
        "title": "Slice 1B1 — import-loader comparable periods",
        "report": "235b_section1b1_import_loader_periods_report.md",
        "focus": ROOT / "235b_eval_section1b1_focus.txt",
        "fallback": None,
    },
    "1b2": {
        "title": "Slice 1B2 — import-loader accounting tests",
        "report": "235b_section1b2_import_loader_tests_report.md",
        "focus": ROOT / "235b_eval_section1b2_focus.txt",
        "fallback": None,
    },
    "1c1": {
        "title": "Slice 1C1 — Python import_loader.py",
        "report": "235b_section1c1_import_loader_py_report.md",
        "focus": ROOT / "235b_eval_section1c1_focus.txt",
        "fallback": None,
    },
    "1c2": {
        "title": "Slice 1C2 — import_sync + practice_source_access",
        "report": "235b_section1c2_import_sync_report.md",
        "focus": ROOT / "235b_eval_section1c2_focus.txt",
        "fallback": None,
    },
    "2a1": {
        "title": "Slice 2A1 — hal-skills widget validation",
        "report": "235b_section2a1_hal_skills_report.md",
        "focus": ROOT / "235b_eval_section2a1_focus.txt",
        "fallback": None,
    },
    "2a2": {
        "title": "Slice 2A2 — widget-contract.js",
        "report": "235b_section2a2_widget_contract_report.md",
        "focus": ROOT / "235b_eval_section2a2_focus.txt",
        "fallback": None,
    },
    "2b1": {
        "title": "Slice 2B1 — hal-widget-master-chart.js",
        "report": "235b_section2b1_master_chart_report.md",
        "focus": ROOT / "235b_eval_section2b1_focus.txt",
        "fallback": None,
    },
    "2b2": {
        "title": "Slice 2B2 — import-loader financial dashboard build",
        "report": "235b_section2b2_financial_dashboard_report.md",
        "focus": ROOT / "235b_eval_section2b2_focus.txt",
        "fallback": None,
    },
    "2c1": {
        "title": "Slice 2C1 — page-canvas.js",
        "report": "235b_section2c1_page_canvas_report.md",
        "focus": ROOT / "235b_eval_section2c1_focus.txt",
        "fallback": None,
    },
    "2c2": {
        "title": "Slice 2C2 — hal-page + validate-hal.mjs",
        "report": "235b_section2c2_hal_page_validate_report.md",
        "focus": ROOT / "235b_eval_section2c2_focus.txt",
        "fallback": None,
    },
}

SECTION_PROMPTS: dict[str, str] = {
    "1": """Review Section 1 only: backend data/import/widget pipeline.
Business rules:
- QuickBooks supplies revenue, expenses, net income, accounting/AP/reconciliation context.
- SoftDent supplies production, collections, claims, patient/practice operational data, and dental A/R.
- Dental A/R must come from explicit SoftDent A/R exports only.
- Do not synthesize dental A/R as production minus collections.
- Widget feed should match imported/cache data used by the financial summary.
- Empty or partial imports must not produce misleading SUCCESS widgets.
- Missing A/R should remain null/unavailable, not fake zero.
Find source-mapping bugs, persistence/staleness bugs, misleading status bugs, null issues, security regressions, API/frontend mismatches, and test gaps.
Do NOT review only models.py in isolation. Do NOT write setup guides.""",
    "2": """Review Section 2 only: frontend dashboard/widget rendering.
Focus on:
- SUCCESS-only HAL widget overrides vs local KPI fallback
- SoftDent A/R rendering (null/unavailable vs fake zero)
- QuickBooks vs SoftDent source labels and coverage panels
- Widget feed source labels (Import cache / HAL feed / Local KPI)
- Schema mismatch risks between API client types and dashboard rendering
- Misleading UI when backend returns partial or missing data
Find rendering bugs, fallback logic bugs, misleading labels, null-to-zero coercion, and test gaps.
Do NOT write generic Zod tutorials or setup guides.""",
    "3": """Review Section 3 only: local AI lane routing and runtime scripts.
Focus on frontend lane 24B (:11434), backend lane 30B (:11435), evaluator lane (:11436) separation,
unavailable errors, foreground process lifetime, docs/scripts/config alignment.
Do NOT write setup guides.""",
    "4": """Review Section 4 only: security and configuration.
Focus on widget update auth, local model artifact safety, secrets handling, .env.example safety,
unauthenticated endpoints, oversized payload protections, runtime cache persistence risks.
Do NOT write setup guides.""",
    "5": """Review Section 5 only: tests and documentation consistency.
Focus on stale mocks, tests that pass while runtime fails, docs implying wrong lane behavior,
missing regression tests for A/R, widget feed, AI lanes, and model scripts.
Do NOT write setup guides.""",
    "1a": """Review Section 1A only: SoftDent period sync and collections pipeline.
Focus on collectionsPending vs collectionsReported, comparable period alignment with QuickBooks,
daysheet upserts, production-only months, and stale dashboard rows.
Do NOT write setup guides.""",
    "1b": """Review Section 1B only: site import-loader comparable periods and accounting rules.
Focus on resolveComparablePeriod, assessCollectionHealth, buildFinancialDashboard,
misleading SUCCESS when collections are pending, and period mismatch bugs.
Do NOT write setup guides.""",
    "1c": """Review Section 1C only: Python import loader and practice source access.
Focus on import_sync, direct pipeline wiring, cache manifest freshness, and source path resolution.
Do NOT write setup guides.""",
    "2a": """Review Section 2A only: HAL skills and widget contract validation.
Focus on practiceFinancialOverview degraded logic, widgetContractApi usage, pending collections info level.
Do NOT write setup guides.""",
    "2b": """Review Section 2B only: practice financial overview widgets and master chart rendering.
Focus on null vs zero, source labels, partial import UX, and chart data binding.
Do NOT write setup guides.""",
    "2c": """Review Section 2C only: page canvas and HAL page validation.
Focus on validate-hal.mjs expectations, page-canvas wiring, and schema mismatches.
Do NOT write setup guides.""",
    "1a1": """Review slice 1A1 only: softdent_dashboard_period_sync.py period rows and collections flags.
Focus on _include_collections_from_source, _build_period_row, collectionsPending vs collectionsReported,
_explicit_collections_failure, sync_dashboard_period_rows upsert merge. Max 2-3 findings.""",
    "1a2": """Review slice 1A2 only: import_direct_pipeline.py and period sync tests.
Focus on period export ingestion, daysheet upserts, and test gaps for collections pending scenarios.""",
    "1b1": """Review slice 1B1 only: import-loader.js comparable period and collection health logic.
Focus on resolveComparablePeriod, resolveDashboardPeriodContext, assessCollectionHealth, buildFinancialDashboard.""",
    "1b2": """Review slice 1B2 only: test_import_loader_accounting.mjs.
Focus on missing regressions for pending collections, period mismatch, and misleading SUCCESS cases.""",
    "1c1": """Review slice 1C1 only: import_loader.py.
Focus on cache manifest, dashboard JSON loading, and source path resolution bugs.""",
    "1c2": """Review slice 1C2 only: import_sync.py and practice_source_access.py.
Focus on direct pipeline wiring, bridge paths, and stale import cache risks.""",
    "2a1": """Review slice 2A1 only: hal-skills.js.
Focus on practiceFinancialOverview validation, degraded vs success, widgetContractApi usage.""",
    "2a2": """Review slice 2A2 only: widget-contract.js.
Focus on pending collections display, contract status labels, and misleading success states.""",
    "2b1": """Review slice 2B1 only: hal-widget-master-chart.js.
Focus on null vs zero, partial data binding, and source label accuracy.""",
    "2b2": """Review slice 2B2 only: import-loader.js financial overview sections.
Focus on collectionsPendingValue, displayAggregate, and practice overview widget feed.""",
    "2c1": """Review slice 2C1 only: page-canvas.js.
Focus on widget wiring, schema mismatches, and partial import UX.""",
    "2c2": """Review slice 2C2 only: hal-page.js and validate-hal.mjs.
Focus on validator expectations vs runtime page behavior and missing regression tests.""",
}

SYSTEM = (
    "Senior full-stack auditor. Evidence-based only. Never invent files. "
    "Do NOT show reasoning, planning, or step-by-step analysis. "
    "Output ONLY finalized audit findings — no preamble. "
    "Each finding MUST use this exact structure:\n"
    "### Finding N: <title>\n"
    "- **Severity:** Critical|High|Medium|Low\n"
    "- **Files/functions:** ...\n"
    "- **Evidence:** ...\n"
    "- **Recommended narrow fix:** ...\n"
    "- **Test to add or run:** ...\n"
    "Label speculative findings as speculative. "
    "End with: **Code changes recommended now:** yes|no — <one sentence rationale>."
)

SETUP_GUIDE_MARKERS = (
    "step 1:",
    "open **powershell",
    "recommended setup",
    "run `ollama serve`",
    "dotnet run",
)


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + "\n\n...[truncated]...\n\n" + text[-half:]


def lane_reachable(url: str, timeout: float = 5.0) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/v1/models", timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def verify_lane_isolation(isolated: bool) -> dict[str, bool]:
    frontend_up = lane_reachable(FRONTEND_URL)
    backend_up = lane_reachable(BACKEND_URL)
    evaluator_up = lane_reachable(EVALUATOR_URL)

    if isolated:
        if frontend_up or backend_up:
            raise RuntimeError(
                "Normal lanes must be stopped before 235B evaluation. "
                f":11434 up={frontend_up}, :11435 up={backend_up}"
            )
        if not evaluator_up:
            raise RuntimeError(f"Evaluator lane unreachable at {EVALUATOR_URL}")

    return {
        "normal_lanes_stopped": not frontend_up and not backend_up,
        "only_235b_running": evaluator_up and not frontend_up and not backend_up,
        "evaluator_up": evaluator_up,
    }


def preflight_model() -> None:
    with urllib.request.urlopen(f"{EVALUATOR_URL}/v1/models", timeout=15) as resp:
        models = json.loads(resp.read().decode("utf-8"))
    ids = {item.get("id") for item in models.get("data", [])}
    if MODEL not in ids:
        raise RuntimeError(f"{MODEL} not listed on {EVALUATOR_URL}. Available: {sorted(x for x in ids if x)}")


def call_ollama(user_prompt: str, *, max_tokens: int = 4096) -> tuple[str, dict]:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "think": False,
        "options": {"temperature": 0.1, "num_predict": max_tokens},
    }
    req = urllib.request.Request(
        f"{EVALUATOR_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    msg = body.get("message", {})
    content = (msg.get("content") or "").strip()
    return content or "(empty response)", body


def validate_answer(answer: str) -> list[str]:
    errors: list[str] = []
    lowered = answer.lower()
    if not answer or answer == "(empty response)":
        errors.append("empty model response")
    if "severity" not in lowered and "**severity:**" not in lowered:
        errors.append("missing Severity labels in findings")
    if "finding 1" not in lowered and "### finding" not in lowered:
        errors.append("missing numbered Finding sections")
    if any(marker in lowered for marker in SETUP_GUIDE_MARKERS):
        errors.append("looks like a setup guide, not an audit")
    return errors


def pick_context(primary: Path, fallback: Path | None) -> tuple[Path, str]:
    if primary.exists() and primary.stat().st_size > 0:
        path = primary
    elif fallback and fallback.exists():
        path = fallback
    else:
        raise FileNotFoundError(f"Missing context file: {primary}")
    return path, path.read_text(encoding="utf-8", errors="replace")


def scope_from_context(context_path: Path) -> str:
    headers = re.findall(r"^=== (.+?) ===", context_path.read_text(encoding="utf-8", errors="replace"), flags=re.MULTILINE)
    if headers:
        return ", ".join(headers[:12]) + (" ..." if len(headers) > 12 else "")
    return context_path.name


def build_report(
    *,
    meta: dict[str, str | Path | None],
    context_path: Path,
    lane_state: dict[str, bool],
    answer: str,
    validation_errors: list[str],
) -> str:
    now = datetime.now(timezone.utc).isoformat()
    title = str(meta["title"])
    scope = scope_from_context(context_path)
    stopped = "yes" if lane_state.get("normal_lanes_stopped") else "no"
    only_235b = "yes" if lane_state.get("only_235b_running") else "no"
    credible_note = "See model output below." if not validation_errors else f"Validation issues: {', '.join(validation_errors)}"

    return f"""# {title}

## Section metadata

- Generated (UTC): {now}
- Model: `{MODEL}` @ `{EVALUATOR_URL}`
- Context file: `{context_path.name}`
- 24B/30B stopped before run: {stopped}
- Only 235B running during evaluation: {only_235b}

## Section name

{title}

## Scope/files reviewed

{scope}

## Whether 24B/30B were stopped first

{stopped}

## Whether only 235B was running

{only_235b}

## Top findings

{answer}

## Credible vs low-confidence findings

{credible_note}

Review each numbered finding above. Treat findings without direct code evidence as low-confidence.

## Evidence from code

See per-finding Evidence fields in the model output above.

## Recommended narrow fixes

See per-finding fix recommendations in the model output above.

## Tests to add/run

See per-finding test recommendations in the model output above.

## Whether code changes are recommended now

Defer code changes until the section report is reviewed and approved. Apply only narrow fixes tied to credible High/Critical findings.

---
*235B sectional audit artifact — do not commit unless explicitly approved.*
"""


def run_section(key: str, *, isolated: bool, overwrite: bool) -> int:
    meta = SECTION_META[key]
    report_path = ROOT / str(meta["report"])
    debug_path = ROOT / f"235b_section{key}.raw.json"
    ctx_cache = ROOT / f"235b_ctx_section{key}.txt"

    if report_path.exists() and not overwrite:
        raise FileExistsError(
            f"Report already exists: {report_path}. Pass --overwrite to replace it."
        )

    print("Lane isolation check...", flush=True)
    lane_state = verify_lane_isolation(isolated)

    print("Model preflight...", flush=True)
    preflight_model()

    context_path, context_raw = pick_context(Path(str(meta["focus"])), Path(str(meta["fallback"])) if meta["fallback"] else None)
    context_limit = context_limit_for(key)
    context = truncate(context_raw, context_limit)
    ctx_cache.write_text(context, encoding="utf-8")
    print(f"Context: {context_path.name} ({len(context)} chars) -> {ctx_cache.name}", flush=True)

    section_prompt = SECTION_PROMPTS[key]
    if key in SLICE_SECTIONS:
        finding_cap = "Return 2-3 audit findings max."
        max_tokens = 1536
    elif key in MICRO_SECTIONS:
        finding_cap = "Return 2-5 audit findings max."
        max_tokens = 3072
    else:
        finding_cap = "Return 3-8 audit findings max."
        max_tokens = 4096
    format_block = (
        "Use ONLY the Finding template from the system prompt. "
        "No chain-of-thought. No 'We are reviewing'. Start directly with '### Finding 1:'."
    )
    user_prompt = (
        f"{section_prompt}\n\n"
        f"{finding_cap} {format_block}\n\n"
        f"--- CODE ---\n{context}\n--- END ---"
    )

    print(f"Evaluating section {key}...", flush=True)
    answer, raw = call_ollama(user_prompt, max_tokens=max_tokens)
    validation_errors = validate_answer(answer)
    if validation_errors:
        print(f"First pass validation: {', '.join(validation_errors)} — retrying...", flush=True)
        retry_prompt = (
            f"{user_prompt}\n\n"
            "Your prior answer failed validation. Rewrite using ONLY ### Finding N blocks "
            "with **Severity:** lines. No reasoning text."
        )
        answer, raw = call_ollama(retry_prompt, max_tokens=max_tokens)
    debug_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    validation_errors = validate_answer(answer)
    if validation_errors:
        print(f"Warning: {', '.join(validation_errors)}", flush=True)
        print(f"Raw response saved: {debug_path}", flush=True)

    report = build_report(
        meta=meta,
        context_path=context_path,
        lane_state=lane_state,
        answer=answer,
        validation_errors=validation_errors,
    )
    report_path.write_text(report, encoding="utf-8")
    print(f"Report saved: {report_path}", flush=True)
    return 1 if validation_errors and "empty model response" in validation_errors[0] else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one isolated 235B audit section.")
    parser.add_argument("section", choices=sorted(SECTION_META.keys()), help="Section number 1-5")
    parser.add_argument(
        "--isolated",
        action="store_true",
        help="Require normal lanes down and evaluator lane up (use with scripts/run_235b_isolated_section.ps1)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing section report file if present.",
    )
    args = parser.parse_args()
    try:
        return run_section(args.section, isolated=args.isolated, overwrite=args.overwrite)
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
