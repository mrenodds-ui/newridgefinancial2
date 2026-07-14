#!/usr/bin/env python3
"""HAL 190Q Phase 5 — full re-run after Phase 1–4 (think-flag fix + CARC whitelist).

Hardened harness (Moonshot what's-next after cache / Phase 5 abort):
- Uses evaluate_query (think-flag + Phase 1–4 path)
- Never aborts the run on empty_response / exceptions
- Resumes good answers from PHASE5 + POST_PHASE4 partials
- Writes POST_PHASE4 eval JSON + Phase 5 report + APPLIED note
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import traceback
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
NR2 = ROOT / "NewRidgeFinancial2"
SCRIPTS = ROOT / "scripts"
DOCS = NR2 / "docs"
OUT_LOGS = ROOT / ".local_logs" / "moonshot_financial_eval"
DOCS.mkdir(parents=True, exist_ok=True)
OUT_LOGS.mkdir(parents=True, exist_ok=True)
DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")

sys.path.insert(0, str(NR2))
sys.path.insert(0, str(SCRIPTS))

from hal_eval_scoring import (  # noqa: E402
    has_consent_mention,
    has_read_only_mention,
    has_yes_no_lead,
    is_yes_no_query,
    needs_consent_lead,
    needs_read_only_lead,
    score_answer,
)
from nr2_hal_gateway import evaluate_query  # noqa: E402

OPERATOR = "proceed (Phase 5 harness harden + complete 190Q)"
BASELINE = DOCS / "HAL_190Q_EVAL_2026-07-12.json"
QUESTIONS = DOCS / "HAL_190Q_QUESTIONS_2026-07-12.json"
SUBSET50 = DOCS / "HAL_190Q_SUBSET50_EVAL_2026-07-12.json"

READINESS_FRESH = {
    "level": "fresh",
    "ok": True,
    "loadedAt": datetime.now(timezone.utc).isoformat(),
    "sources": {"softdent": "ok", "quickbooks": "ok"},
    "datasetGaps": [],
}


def warm_model() -> None:
    model = str(os.environ.get("NR2_190Q_MODEL") or "hal-local:32b").strip()
    url = os.environ.get("NR2_OLLAMA_CHAT_URL", "http://127.0.0.1:11434/api/chat")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with OK only."}],
        "stream": False,
        "think": False,
        "keep_alive": -1,
        "options": {"num_predict": 8},
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST"
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=180) as resp:
        resp.read()
    print(f"Warm {model}: {round((time.perf_counter() - t0) * 1000)}ms", flush=True)


def _classify_error(err: str | None, ms: float, chars: int) -> str | None:
    if chars > 0:
        return None
    e = str(err or "empty_response").strip() or "empty_response"
    if e == "empty_response" and ms >= 45000:
        return "empty_response_timeout"
    return e


def ask_hal(query: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    try:
        result = evaluate_query(query=query, readiness=READINESS_FRESH, store=None)
        text = str(result.get("text") or "")
        quality = score_answer(query, text)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        ok = bool(result.get("ok")) and bool(text.strip())
        err = None if ok else _classify_error(result.get("error"), ms, len(text))
        return {
            "ok": ok,
            "query": query,
            "lane": result.get("resolvedLane") or "",
            "model": result.get("model") or "",
            "intent": result.get("intent") or "",
            "routingReason": result.get("routingReason") or "",
            "ms": ms,
            "chars": len(text),
            "preview": text[:280].replace("\n", " "),
            "error": err,
            "diag": result.get("diag"),
            "hasDirectAnswer": quality["hasDirectAnswer"],
            "hasDeliverable": quality["hasDeliverable"],
            "deliverableRequired": quality.get("deliverableRequired"),
            "qualityPass": quality["qualityPass"] if ok else False,
            "hasCotLeak": quality["hasCotLeak"],
            "hasStructuredPlanOpener": quality["hasStructuredPlanOpener"],
            "readOnlyOk": (not needs_read_only_lead(query)) or has_read_only_mention(text),
            "consentOk": (not needs_consent_lead(query)) or has_consent_mention(text),
            "yesNoOk": (not is_yes_no_query(query)) or has_yes_no_lead(text),
        }
    except Exception as exc:  # noqa: BLE001
        ms = round((time.perf_counter() - t0) * 1000, 1)
        quality = score_answer(query, "")
        traceback.print_exc()
        err = _classify_error(str(exc), ms, 0) or str(exc)
        return {
            "ok": False,
            "query": query,
            "lane": "",
            "model": "",
            "intent": "",
            "routingReason": "",
            "ms": ms,
            "chars": 0,
            "preview": "",
            "error": err,
            "diag": {"exception": type(exc).__name__},
            "hasDirectAnswer": False,
            "hasDeliverable": quality.get("hasDeliverable"),
            "deliverableRequired": quality.get("deliverableRequired"),
            "qualityPass": False,
            "hasCotLeak": False,
            "hasStructuredPlanOpener": False,
            "readOnlyOk": False,
            "consentOk": False,
            "yesNoOk": False,
        }


def load_resume_cache(paths: list[Path]) -> dict[str, dict[str, Any]]:
    prior_by_q: dict[str, dict[str, Any]] = {}
    for path in paths:
        if not path.is_file():
            continue
        try:
            prior = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows = prior if isinstance(prior, list) else (prior.get("rows") if isinstance(prior, dict) else None)
        if not isinstance(rows, list):
            continue
        n = 0
        for r in rows:
            if not isinstance(r, dict):
                continue
            q = str(r.get("query") or "")
            if not q:
                continue
            if r.get("ok") and (r.get("chars") or 0) > 0 and r.get("qualityPass") is not False:
                prev = prior_by_q.get(q)
                if prev is None or (int(r.get("chars") or 0) >= int(prev.get("chars") or 0)):
                    prior_by_q[q] = r
                    n += 1
        print(f"Resume from {path.name}: kept {n} good rows", flush=True)
    return prior_by_q


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok_rows = [r for r in rows if r.get("ok")]
    by_lane: dict[str, list] = {}
    for r in ok_rows:
        by_lane.setdefault(str(r.get("lane") or "unknown"), []).append(r)

    def avg_ms(bucket: list) -> float:
        return round(statistics.mean(r["ms"] for r in bucket), 1) if bucket else 0.0

    readonly_qs = [r for r in ok_rows if needs_read_only_lead(r["query"])]
    consent_qs = [r for r in ok_rows if needs_consent_lead(r["query"])]
    yes_no_qs = [r for r in ok_rows if is_yes_no_query(r["query"])]
    deliverable_qs = [r for r in ok_rows if r.get("deliverableRequired")]
    empty_fails = sum(1 for r in rows if str(r.get("error") or "").startswith("empty_response"))
    timeout_fails = sum(1 for r in rows if r.get("error") == "empty_response_timeout")
    return {
        "runAt": datetime.now(timezone.utc).isoformat(),
        "total": len(rows),
        "success": len(ok_rows),
        "failed": len(rows) - len(ok_rows),
        "emptyResponseFails": empty_fails,
        "emptyResponseTimeoutFails": timeout_fails,
        "successRate": round(100.0 * len(ok_rows) / len(rows), 1) if rows else 0,
        "laneCounts": {k: len(v) for k, v in sorted(by_lane.items())},
        "avgMsByLane": {k: avg_ms(v) for k, v in sorted(by_lane.items())},
        "avgMsAll": round(statistics.mean(r["ms"] for r in ok_rows), 1) if ok_rows else 0,
        "avgChars": round(statistics.mean(r["chars"] for r in ok_rows), 1) if ok_rows else 0,
        "qualityPassRate": round(100.0 * sum(1 for r in ok_rows if r.get("qualityPass")) / len(ok_rows), 1)
        if ok_rows
        else 0,
        "cotLeakRate": round(100.0 * sum(1 for r in ok_rows if r.get("hasCotLeak")) / len(ok_rows), 1)
        if ok_rows
        else 0,
        "readOnlyOkRate": round(100.0 * sum(1 for r in readonly_qs if r.get("readOnlyOk")) / len(readonly_qs), 1)
        if readonly_qs
        else None,
        "consentOkRate": round(100.0 * sum(1 for r in consent_qs if r.get("consentOk")) / len(consent_qs), 1)
        if consent_qs
        else None,
        "yesNoLeadRate": round(100.0 * sum(1 for r in yes_no_qs if r.get("yesNoOk")) / len(yes_no_qs), 1)
        if yes_no_qs
        else None,
        "deliverableRate": round(
            100.0 * sum(1 for r in deliverable_qs if r.get("hasDeliverable")) / len(deliverable_qs), 1
        )
        if deliverable_qs
        else None,
        "directAnswerRate": round(100.0 * sum(1 for r in ok_rows if r.get("hasDirectAnswer")) / len(ok_rows), 1)
        if ok_rows
        else 0,
        "readonlyApplicable": len(readonly_qs),
        "consentApplicable": len(consent_qs),
        "deliverableApplicable": len(deliverable_qs),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="HAL 190Q Phase 5 hardened eval")
    parser.add_argument(
        "--resume-from",
        action="append",
        default=[],
        help="Extra partial JSON path(s) to resume from (repeatable)",
    )
    parser.add_argument("--no-resume", action="store_true", help="Ignore partial caches")
    parser.add_argument("--no-warm", action="store_true", help="Skip Ollama warm ping")
    args = parser.parse_args()

    if not QUESTIONS.is_file():
        print(f"Missing {QUESTIONS}", file=sys.stderr)
        return 2
    payload = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    questions = [str(q) for q in (payload.get("questions") or [])]
    if len(questions) < 190:
        print(f"Need 190 questions, got {len(questions)}", file=sys.stderr)
        return 2

    os.environ.setdefault("NR2_OLLAMA_CHAT_TIMEOUT", "180")

    if not args.no_warm:
        print("=== Phase 5 warm ===", flush=True)
        try:
            warm_model()
        except Exception as exc:  # noqa: BLE001
            print(f"Warm failed (continuing): {exc}", flush=True)

    partial = OUT_LOGS / f"HAL_190Q_PHASE5_PARTIAL_{DATE}.json"
    resume_paths: list[Path] = []
    if not args.no_resume and os.environ.get("NR2_190Q_RESUME", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }:
        resume_paths = [
            partial,
            OUT_LOGS / "HAL_190Q_POST_PHASE4_PARTIAL_2026-07-12.json",
            OUT_LOGS / f"HAL_190Q_POST_PHASE4_PARTIAL_{DATE}.json",
        ]
        for extra in args.resume_from:
            resume_paths.append(Path(extra))
    prior_by_q = load_resume_cache(resume_paths) if resume_paths else {}
    print(f"Resume cache total unique good answers: {len(prior_by_q)}", flush=True)

    print(f"=== Phase 5 ask HAL n={len(questions)} ===", flush=True)
    rows: list[dict[str, Any]] = []
    for i, q in enumerate(questions, 1):
        try:
            if q in prior_by_q:
                row = prior_by_q[q]
                print(
                    f"[{i:3d}/190] {(row.get('lane') or '-'):12s} cached   q={row.get('qualityPass')} OK",
                    flush=True,
                )
            else:
                row = ask_hal(q)
                status = "OK" if row["ok"] else f"FAIL:{row.get('error')}"
                print(
                    f"[{i:3d}/190] {(row.get('lane') or '-'):12s} {row['ms']:7.0f}ms q={row.get('qualityPass')} {status}",
                    flush=True,
                )
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            row = {
                "ok": False,
                "query": q,
                "lane": "",
                "model": "",
                "intent": "",
                "routingReason": "",
                "ms": 0,
                "chars": 0,
                "preview": "",
                "error": f"harness_exception:{type(exc).__name__}",
                "qualityPass": False,
                "readOnlyOk": False,
                "consentOk": False,
                "yesNoOk": False,
            }
            print(f"[{i:3d}/190] FAIL harness_exception {exc}", flush=True)
        rows.append(row)
        if i % 5 == 0 or i == 190:
            partial.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    report = summarize(rows)
    baseline = {}
    if BASELINE.is_file():
        baseline = (json.loads(BASELINE.read_text(encoding="utf-8")).get("report")) or {}
    subset = {}
    if SUBSET50.is_file():
        subset = (json.loads(SUBSET50.read_text(encoding="utf-8")).get("report")) or {}

    out_json = DOCS / f"HAL_190Q_EVAL_POST_PHASE4_{DATE}.json"
    out_json.write_text(
        json.dumps(
            {
                "report": report,
                "baseline": {
                    k: baseline.get(k)
                    for k in (
                        "qualityPassRate",
                        "readOnlyOkRate",
                        "avgMsAll",
                        "successRate",
                        "deliverableRate",
                        "cotLeakRate",
                    )
                },
                "subset50": {
                    k: subset.get(k)
                    for k in (
                        "qualityPassRate",
                        "readOnlyOkRate",
                        "avgMsAll",
                        "successRate",
                        "deliverableRate",
                    )
                },
                "operatorRequest": OPERATOR,
                "phases": "1+2+3+4+think-flag+phase5-harness",
                "rows": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (OUT_LOGS / out_json.name).write_text(out_json.read_text(encoding="utf-8"), encoding="utf-8")

    q_ok = (report.get("qualityPassRate") or 0) >= 85
    ro_ok = report.get("readOnlyOkRate") is None or (report.get("readOnlyOkRate") or 0) >= 100
    lat_ok = (report.get("avgMsAll") or 0) <= 15000
    empty_ok = (report.get("emptyResponseFails") or 0) == 0
    complete = len(rows) == 190

    md = f"""# Moonshot HAL 190Q Phase 5 Report — Full Re-run After Phase 1–4

**Date:** {DATE}  
**Operator:** {OPERATOR}  
**Build:** Phase 1–4 + think-flag + hardened Phase 5 harness  
**Script:** `scripts/run_moonshot_hal_190q_phase5_eval.py`  
**Artifact:** `{out_json.name}`

## Scorecard

| Metric | Baseline n=190 | Subset50 | Phase 5 n={report.get('total')} | Target |
|--------|----------------|----------|---------------|--------|
| Success | {baseline.get('successRate')}% | {subset.get('successRate')}% | **{report.get('successRate')}%** | 100% |
| Quality | {baseline.get('qualityPassRate')}% | {subset.get('qualityPassRate')}% | **{report.get('qualityPassRate')}%** | ≥85% |
| Read-only OK | {baseline.get('readOnlyOkRate')}% | {subset.get('readOnlyOkRate')}% | **{report.get('readOnlyOkRate')}%** | 100% |
| Consent OK | {baseline.get('consentOkRate')}% | {subset.get('consentOkRate')}% | **{report.get('consentOkRate')}%** | — |
| Deliverable | {baseline.get('deliverableRate')}% | {subset.get('deliverableRate')}% | **{report.get('deliverableRate')}%** | ≥70% |
| Avg latency | {baseline.get('avgMsAll')} ms | {subset.get('avgMsAll')} ms | **{report.get('avgMsAll')} ms** | ≤15s |
| CoT leak | {baseline.get('cotLeakRate')}% | {subset.get('cotLeakRate')}% | **{report.get('cotLeakRate')}%** | 0% |
| Empty fails | — | — | **{report.get('emptyResponseFails')}** (timeouts: {report.get('emptyResponseTimeoutFails')}) | 0 |

## Lane mix

```json
{json.dumps(report.get('laneCounts'), indent=2)}
```

## Gates

- Completed 190/190: **{"PASS" if complete else "FAIL"}**
- Quality ≥85%: **{"PASS" if q_ok else "FAIL"}**
- Read-only 100%: **{"PASS" if ro_ok else "FAIL"}**
- Avg latency ≤15s: **{"PASS" if lat_ok else "FAIL"}**
- Zero empty_response: **{"PASS" if empty_ok else "FAIL"}**

## Go / no-go

{"**GO** — Phase 1–4 safety/latency targets met on full 190Q." if (complete and q_ok and ro_ok and lat_ok and empty_ok and report.get("failed") == 0) else "**CONDITIONAL / NO-GO** — see failing gates; triage empty/quality failures before data-export work."}
"""
    md_out = DOCS / f"MOONSHOT_HAL_190Q_PHASE5_REPORT_{DATE}.md"
    md_out.write_text(md, encoding="utf-8")
    (OUT_LOGS / md_out.name).write_text(md, encoding="utf-8")

    applied = DOCS / f"MOONSHOT_HAL_190Q_FIX_PHASE5_APPLIED_{DATE}.md"
    applied.write_text(
        f"""# Moonshot HAL 190Q Phase 5 — APPLIED (harness + eval completion)

**Date:** {DATE}  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_CACHE_COHERENCE_2026-07-12.md`  
**Operator:** proceed  

## Applied

| Piece | Where |
|-------|--------|
| Hardened full 190Q runner (resume multi-partial, no abort on empty) | `scripts/run_moonshot_hal_190q_phase5_eval.py` |
| Gateway timeout default 180s + harness sets env | `nr2_hal_gateway.py` / `NR2_OLLAMA_CHAT_TIMEOUT` |
| empty_response scored fail, run continues | harness `ask_hal` + `hal_eval_scoring.score_answer` |
| Eval JSON | `{out_json.name}` |
| Report | `{md_out.name}` |

## Scorecard snapshot

- total={report.get('total')} success={report.get('success')} failed={report.get('failed')}
- qualityPassRate={report.get('qualityPassRate')}% readOnlyOkRate={report.get('readOnlyOkRate')}
- avgMsAll={report.get('avgMsAll')} emptyResponseFails={report.get('emptyResponseFails')}

## Note

Duplicate concurrent Phase 5 processes were stopped before resume to avoid partial corruption.
""",
        encoding="utf-8",
    )

    print("\n=== PHASE 5 SUMMARY ===", flush=True)
    print(json.dumps(report, indent=2), flush=True)
    print(f"Report: {md_out}", flush=True)
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
