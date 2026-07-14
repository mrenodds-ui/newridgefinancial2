#!/usr/bin/env python3
"""Live 190Q subset re-run (n=50) after Phase 1–3 — measure lift vs baseline.

Reuses HAL_190Q_QUESTIONS_*.json. Asks via nr2_hal_gateway.evaluate_query
(local policy + deliverable schema + constraints). Writes subset JSON + comparison MD.
"""

from __future__ import annotations

import json
import os
import random
import re
import statistics
import sys
import time
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
from nr2_hal_gateway import evaluate_query, is_deliverable_request  # noqa: E402

OPERATOR_REQUEST = "proceed (live 190Q subset re-run after Phase 1–3)"
BASELINE_PATH = DOCS / "HAL_190Q_EVAL_2026-07-12.json"
QUESTIONS_PATH = DOCS / "HAL_190Q_QUESTIONS_2026-07-12.json"
N = int(os.environ.get("NR2_190Q_SUBSET_N") or "50")
SEED = int(os.environ.get("NR2_190Q_SUBSET_SEED") or "19050")

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


def pick_subset(questions: list[str], n: int) -> list[str]:
    """Stratified-ish sample: force-include safety/deliverable buckets, then fill."""
    rng = random.Random(SEED)
    buckets: dict[str, list[str]] = {
        "readonly": [],
        "consent": [],
        "deliverable": [],
        "yesno": [],
        "carc": [],
        "other": [],
    }
    for q in questions:
        ql = q.lower()
        if needs_read_only_lead(q):
            buckets["readonly"].append(q)
        elif needs_consent_lead(q):
            buckets["consent"].append(q)
        elif is_deliverable_request(q):
            buckets["deliverable"].append(q)
        elif is_yes_no_query(q):
            buckets["yesno"].append(q)
        elif re.search(r"\b(carc|cas|rarc|835|era)\b", ql):
            buckets["carc"].append(q)
        else:
            buckets["other"].append(q)

    picked: list[str] = []
    seen: set[str] = set()

    def take(bucket: list[str], k: int) -> None:
        rng.shuffle(bucket)
        for q in bucket:
            if len(picked) >= n:
                return
            if q in seen:
                continue
            if k <= 0:
                break
            picked.append(q)
            seen.add(q)
            k -= 1

    # Targets summing ~50
    take(buckets["readonly"], 8)
    take(buckets["consent"], 6)
    take(buckets["deliverable"], 10)
    take(buckets["yesno"], 8)
    take(buckets["carc"], 8)
    take(buckets["other"], n)

    # Fill remainder from any leftover
    rest = [q for q in questions if q not in seen]
    rng.shuffle(rest)
    for q in rest:
        if len(picked) >= n:
            break
        picked.append(q)
        seen.add(q)
    return picked[:n]


def ask_hal(query: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    try:
        result = evaluate_query(query=query, readiness=READINESS_FRESH, store=None)
        text = str(result.get("text") or "")
        quality = score_answer(query, text)
        ok = bool(result.get("ok")) and bool(text.strip())
        return {
            "ok": ok,
            "query": query,
            "lane": result.get("resolvedLane") or "",
            "model": result.get("model") or "",
            "intent": result.get("intent") or "",
            "routingReason": result.get("routingReason") or "",
            "ms": round((time.perf_counter() - t0) * 1000, 1),
            "chars": len(text),
            "preview": text[:280].replace("\n", " "),
            "error": None if ok else (result.get("error") or "empty_response"),
            "hasDirectAnswer": quality["hasDirectAnswer"],
            "hasDeliverable": quality["hasDeliverable"],
            "deliverableRequired": quality.get("deliverableRequired"),
            "qualityPass": quality["qualityPass"],
            "hasCotLeak": quality["hasCotLeak"],
            "hasStructuredPlanOpener": quality["hasStructuredPlanOpener"],
            "readOnlyOk": (not needs_read_only_lead(query)) or has_read_only_mention(text),
            "consentOk": (not needs_consent_lead(query)) or has_consent_mention(text),
            "yesNoOk": (not is_yes_no_query(query)) or has_yes_no_lead(text),
        }
    except Exception as exc:  # noqa: BLE001
        quality = score_answer(query, "")
        return {
            "ok": False,
            "query": query,
            "lane": "",
            "model": "",
            "intent": "",
            "routingReason": "",
            "ms": round((time.perf_counter() - t0) * 1000, 1),
            "chars": 0,
            "preview": "",
            "error": str(exc),
            "hasDirectAnswer": quality["hasDirectAnswer"],
            "hasDeliverable": quality["hasDeliverable"],
            "deliverableRequired": quality.get("deliverableRequired"),
            "qualityPass": False,
            "hasCotLeak": quality["hasCotLeak"],
            "hasStructuredPlanOpener": quality["hasStructuredPlanOpener"],
            "readOnlyOk": False,
            "consentOk": False,
            "yesNoOk": False,
        }


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
    return {
        "runAt": datetime.now(timezone.utc).isoformat(),
        "total": len(rows),
        "success": len(ok_rows),
        "failed": len(rows) - len(ok_rows),
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


def load_baseline() -> dict[str, Any]:
    if not BASELINE_PATH.is_file():
        return {}
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return data.get("report") or {}


def main() -> int:
    if not QUESTIONS_PATH.is_file():
        print(f"Missing questions file: {QUESTIONS_PATH}", file=sys.stderr)
        return 2
    payload = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    questions = [str(q) for q in (payload.get("questions") or [])]
    if len(questions) < N:
        print(f"Need >= {N} questions, got {len(questions)}", file=sys.stderr)
        return 2

    print(f"=== Warm model ===", flush=True)
    try:
        warm_model()
    except Exception as exc:  # noqa: BLE001
        print(f"Warm failed (continuing): {exc}", flush=True)

    subset = pick_subset(questions, N)
    print(f"=== Ask HAL subset n={len(subset)} (seed={SEED}) ===", flush=True)
    rows: list[dict[str, Any]] = []
    prior_by_q: dict[str, dict[str, Any]] = {}
    partial = OUT_LOGS / f"HAL_190Q_SUBSET{N}_PARTIAL_{DATE}.json"
    if partial.is_file() and os.environ.get("NR2_190Q_RESUME", "1").strip() not in {"0", "false", "no"}:
        try:
            prior = json.loads(partial.read_text(encoding="utf-8"))
            if isinstance(prior, list):
                for r in prior:
                    q = str(r.get("query") or "")
                    if q and r.get("ok") and (r.get("chars") or 0) > 0:
                        prior_by_q[q] = r
                print(f"Resume cache: {len(prior_by_q)} good answers", flush=True)
        except Exception:
            prior_by_q = {}

    for i, q in enumerate(subset, 1):
        if q in prior_by_q:
            row = prior_by_q[q]
            print(
                f"[{i:02d}/{N}] {(row.get('lane') or '-'):12s} cached   q={row.get('qualityPass')} OK",
                flush=True,
            )
        else:
            row = ask_hal(q)
            status = "OK" if row["ok"] else f"FAIL:{row.get('error')}"
            print(
                f"[{i:02d}/{N}] {(row.get('lane') or '-'):12s} {row['ms']:7.0f}ms q={row.get('qualityPass')} {status}",
                flush=True,
            )
        rows.append(row)
        if i % 5 == 0:
            partial.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    partial.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    report = summarize(rows)
    baseline = load_baseline()
    comparison = {
        "metric": ["successRate", "qualityPassRate", "readOnlyOkRate", "consentOkRate", "deliverableRate", "avgMsAll", "cotLeakRate"],
        "baseline": {k: baseline.get(k) for k in ("successRate", "qualityPassRate", "readOnlyOkRate", "consentOkRate", "deliverableRate", "avgMsAll", "cotLeakRate")},
        "subset": {k: report.get(k) for k in ("successRate", "qualityPassRate", "readOnlyOkRate", "consentOkRate", "deliverableRate", "avgMsAll", "cotLeakRate")},
        "targets": {
            "qualityPassRate": 75,
            "readOnlyOkRate": 90,
            "avgMsAll": 45000,
        },
    }

    out_json = DOCS / f"HAL_190Q_SUBSET{N}_EVAL_{DATE}.json"
    out_json.write_text(
        json.dumps(
            {
                "report": report,
                "comparison": comparison,
                "baselineFile": BASELINE_PATH.name,
                "questionsFile": QUESTIONS_PATH.name,
                "subset": subset,
                "rows": rows,
                "operatorRequest": OPERATOR_REQUEST,
                "phases": "1+2+3",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (OUT_LOGS / out_json.name).write_text(out_json.read_text(encoding="utf-8"), encoding="utf-8")

    b = comparison["baseline"]
    s = comparison["subset"]
    md = f"""# Moonshot HAL 190Q Subset Re-run (n={N}) — Phase 1–3 Validation

**Date:** {DATE}  
**Operator:** {OPERATOR_REQUEST}  
**Build:** hal-10561 + Phase 1–3 (`325d24a` / `f225b2b` / `faa3113`)  
**Script:** `scripts/run_moonshot_hal_190q_subset50.py`  
**Questions:** reused `{QUESTIONS_PATH.name}` (seed={SEED})  
**Artifact:** `{out_json.name}`

## Scorecard vs baseline (full 190Q)

| Metric | Baseline (n=190) | Subset (n={N}) | Target |
|--------|------------------|----------------|--------|
| Success rate | {b.get('successRate')}% | **{s.get('successRate')}%** | 100% |
| Quality pass | {b.get('qualityPassRate')}% | **{s.get('qualityPassRate')}%** | ≥75% |
| Read-only OK | {b.get('readOnlyOkRate')}% | **{s.get('readOnlyOkRate')}%** | ≥90% |
| Consent OK | {b.get('consentOkRate')}% | **{s.get('consentOkRate')}%** | ≥90% |
| Deliverable rate | {b.get('deliverableRate')}% | **{s.get('deliverableRate')}%** | ≥70% |
| Avg latency | {b.get('avgMsAll')} ms | **{s.get('avgMsAll')} ms** | <45s |
| CoT leak | {b.get('cotLeakRate')}% | **{s.get('cotLeakRate')}%** | 0% |

## Lane mix (subset)

```json
{json.dumps(report.get('laneCounts'), indent=2)}
```

## Go / no-go for Phase 4

- Quality ≥75%: **{"PASS" if (report.get("qualityPassRate") or 0) >= 75 else "FAIL"}**
- Read-only ≥90%: **{"PASS" if (report.get("readOnlyOkRate") is None or (report.get("readOnlyOkRate") or 0) >= 90) else "FAIL"}**
- Avg latency <45s: **{"PASS" if (report.get("avgMsAll") or 0) < 45000 else "FAIL"}**

If quality/read-only miss targets, Phase 4 CARC briefs + failure triage next.  
If targets hit, prefer full n=190 burn-in or Phase 4 as polish only.
"""
    md_out = DOCS / f"MOONSHOT_HAL_190Q_SUBSET{N}_REPORT_{DATE}.md"
    md_out.write_text(md, encoding="utf-8")
    (OUT_LOGS / md_out.name).write_text(md, encoding="utf-8")

    print("\n=== SUMMARY ===", flush=True)
    print(json.dumps(report, indent=2), flush=True)
    print(f"\nReport: {md_out}", flush=True)
    print(f"JSON: {out_json}", flush=True)
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
