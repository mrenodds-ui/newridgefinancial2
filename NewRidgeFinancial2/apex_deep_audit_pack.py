"""
Phase U0 — Deep Audit & Forecast (Moonshot REAUDIT3 MUST).

30B deep-lane monthly practice health audit + quarter forecast scaffolding.
Emits schema-validated insights → save_last_insight (SSE/N0 picks up).
Honesty: never invent dollars; gap codes when unified views empty.
Flag: NR2_DEEP_AUDIT (default ON; set 0/false/off to disable).
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GAP_AUDIT_DATA_PENDING = "AUDIT_DATA_PENDING"

AUDIT_SYSTEM_PROMPT = (
    "You are a dental practice CFO AI. Using the provided unified DB snapshot "
    "(production, payroll, collections, AP, net profit), generate a Monthly Practice Health Audit. "
    "Output ONLY valid JSON matching schema: widget_type='alert-banner' or 'trend-chart', "
    "title, data (severity/message or series), source_refs for every number. "
    "If data is missing, set data.value/series values to null and confidence='low' "
    "with gap codes like PRODUCTION_PENDING in the message — never invent dollars. "
    "No PHI. No prose outside JSON."
)

FORECAST_SYSTEM_PROMPT = (
    "You are a dental practice CFO AI. Using the unified DB time-series snapshot, "
    "output ONLY a trend-chart JSON insight for next-quarter outlook. "
    "Historical points may include numbers with source_refs; future forecast points "
    "MUST use value=null with confidence='low' unless the snapshot explicitly provides them — "
    "never invent dollars. No PHI. No prose outside JSON."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def deep_audit_enabled() -> bool:
    raw = str(os.getenv("NR2_DEEP_AUDIT") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _normalize_period(period: str | None) -> str:
    raw = str(period or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}", raw):
        return raw
    return datetime.now(timezone.utc).strftime("%Y-%m")


def period_minus_months(period: str, months: int) -> str:
    y, m = int(period[:4]), int(period[5:7])
    m -= int(months)
    while m <= 0:
        m += 12
        y -= 1
    return f"{y:04d}-{m:02d}"


def build_audit_snapshot(
    *,
    period: str | None = None,
    db_path: Path | None = None,
    limit: int = 6,
) -> dict[str, Any]:
    """Non-PHI unified snapshot for deep audit / forecast."""
    period = _normalize_period(period)
    gaps: list[str] = []
    prod_rows: list[dict[str, Any]] = []
    coll_rows: list[dict[str, Any]] = []
    health: list[dict[str, Any]] = []

    try:
        from apex_unified_db_pack import (
            list_collection_vs_ap,
            list_practice_health_snapshots,
            list_production_vs_payroll,
        )

        prod_rows = list_production_vs_payroll(limit=limit, db_path=db_path)
        coll_rows = list_collection_vs_ap(limit=limit, db_path=db_path)
        health = list_practice_health_snapshots(limit=limit, db_path=db_path)
    except Exception as exc:  # noqa: BLE001
        gaps.append(f"UNIFIED_READ_FAILED:{exc}")

    if not prod_rows:
        gaps.append("PRODUCTION_PENDING")
    if not coll_rows:
        gaps.append("COLLECTION_AP_PENDING")
    if not health:
        gaps.append("HEALTH_SNAPSHOT_PENDING")
    if gaps and GAP_AUDIT_DATA_PENDING not in gaps:
        gaps.insert(0, GAP_AUDIT_DATA_PENDING)

    return {
        "ok": True,
        "phase": "U0",
        "period": period,
        "windowStart": period_minus_months(period, max(0, limit - 1)),
        "productionVsPayroll": prod_rows,
        "collectionVsAp": coll_rows,
        "practiceHealth": health,
        "gapCodes": gaps,
        "dataPending": bool(gaps),
        "refreshedAt": _utc_now(),
    }


def build_gap_insight(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Honest alert when unified views lack data — never invent $."""
    period = str(snapshot.get("period") or _normalize_period(None))
    codes = [str(c) for c in (snapshot.get("gapCodes") or []) if c]
    msg = (
        "Deep audit pending imports: "
        + (", ".join(codes[:6]) if codes else GAP_AUDIT_DATA_PENDING)
        + ". Sync SoftDent/QB then re-run. Empty ≠ $0."
    )
    payload = {
        "widget_type": "alert-banner",
        "title": f"Monthly health audit — {period}",
        "data": {
            "severity": "warn",
            "message": msg[:400],
            "value": None,
            "unit": "text",
        },
        "source_refs": [f"nr2:unified:{period}"],
        "confidence": "low",
        "explanation": "U0 gap path — no invented dollars; fix imports then Sync.",
        "action_cta": {"label": "Open SoftDent", "route": "softdent"},
    }
    from apex_structured_insight_pack import validate_insight

    return validate_insight(payload)


def build_historical_trend_insight(snapshot: dict[str, Any]) -> dict[str, Any]:
    """
    Schema-safe trend from mirrored production totals only.
    Forecast placeholders are null (never invent future $).
    """
    period = str(snapshot.get("period") or _normalize_period(None))
    rows = list(snapshot.get("productionVsPayroll") or [])
    series: list[dict[str, Any]] = []
    refs: list[str] = [f"nr2:v_production_vs_payroll:{period}"]
    for row in reversed(rows):
        if not isinstance(row, dict):
            continue
        p = str(row.get("period") or "")
        if not re.fullmatch(r"\d{4}-\d{2}", p):
            continue
        val = row.get("totalProduction")
        series.append(
            {
                "label": p,
                "value": float(val) if isinstance(val, (int, float)) else None,
            }
        )
        refs.append(f"softdent:production:{p}")
    # Next-quarter placeholders — null only
    y, m = int(period[:4]), int(period[5:7])
    for _ in range(3):
        m += 1
        if m > 12:
            m = 1
            y += 1
        series.append({"label": f"{y:04d}-{m:02d}*", "value": None})
    if not series:
        return build_gap_insight(snapshot)
    refs = list(dict.fromkeys(refs))[:12]
    payload = {
        "widget_type": "trend-chart",
        "title": f"Production outlook — {period}",
        "data": {
            "series": series[:24],
            "unit": "dollars",
            "annotations": [
                "Asterisk months are forecast placeholders (null) — never invent $.",
                "Historical values mirrored from v_production_vs_payroll.",
            ],
        },
        "source_refs": refs,
        "confidence": "medium" if any(s.get("value") is not None for s in series) else "low",
        "explanation": "U0 forecast scaffold: history from unified DB; future points null until 30B.",
    }
    from apex_structured_insight_pack import validate_insight

    return validate_insight(payload)


def _persist_audit_log(
    *,
    kind: str,
    lane: str,
    classify_only: bool,
    db_path: Path | None,
) -> str:
    try:
        from apex_unified_db_pack import open_unified, unified_db_path

        flags = json.dumps(["deep_audit", kind, lane, "classify_only" if classify_only else "full"])
        with open_unified(path=db_path) as conn:
            conn.execute(
                """
                INSERT INTO import_health_log
                    (source, export_type, row_count, staleness_hours, gap_flags, detected_at)
                VALUES (?,?,?,?,?,?)
                """,
                ("deep_audit", kind, 1, None, flags, _utc_now()),
            )
            conn.commit()
        return str(db_path or unified_db_path())
    except Exception as exc:  # noqa: BLE001
        return f"log_failed:{exc}"


def _publish_insight(validated: dict[str, Any]) -> dict[str, Any] | None:
    if not validated.get("ok") or not isinstance(validated.get("insight"), dict):
        return None
    insight = validated["insight"]
    try:
        from apex_structured_insight_pack import ai_insight_widget, save_last_insight

        save_last_insight(insight)
        return ai_insight_widget(insight)
    except Exception:
        return None


def generate_monthly_audit(
    *,
    period: str | None = None,
    classify_only: bool = False,
    force_orchestrator: bool | None = None,
    db_path: Path | None = None,
    emit_gap_insight: bool = True,
) -> dict[str, Any]:
    """
    Monthly practice health audit entrypoint.

    classify_only=True never calls Ollama (tests / dry-run).
    On data gaps: emits honest alert-banner to SSE store when emit_gap_insight.
    Full runs: escalate30b via orchestrator with structured JSON required.
    """
    if not deep_audit_enabled():
        return {
            "ok": False,
            "reason": "deep_audit_disabled",
            "hint": "Set NR2_DEEP_AUDIT=1 (default on) to allow deep audits.",
            "phase": "U0",
            "refreshedAt": _utc_now(),
        }

    snapshot = build_audit_snapshot(period=period, db_path=db_path)
    period_n = str(snapshot.get("period"))

    try:
        from apex_orchestrator_pack import orchestrate, orchestrator_enabled
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "reason": f"orchestrator_import:{exc}",
            "phase": "U0",
            "snapshot": snapshot,
            "refreshedAt": _utc_now(),
        }

    enabled = orchestrator_enabled() if force_orchestrator is None else bool(force_orchestrator)
    if not enabled:
        return {
            "ok": False,
            "reason": "orchestrator_disabled",
            "hint": "Set NR2_AI_ORCHESTRATOR=1 (or unset; default ON) for deep-lane audits.",
            "phase": "U0",
            "snapshot": snapshot,
            "refreshedAt": _utc_now(),
        }

    insight_widget = None
    gap_result = None
    if snapshot.get("dataPending") and emit_gap_insight:
        gap_result = build_gap_insight(snapshot)
        insight_widget = _publish_insight(gap_result)

    query = (
        f"Run a monthly practice health audit for {period_n} and cross-reference "
        "SoftDent production/collections with QuickBooks payroll/AP/net profit"
    )
    result = orchestrate(
        query,
        classify_only=classify_only,
        force_enabled=True,
        require_structured=True,
        system_prompt=AUDIT_SYSTEM_PROMPT,
        context={"deepAudit": snapshot, "period": period_n},
    )

    log_path = _persist_audit_log(
        kind="monthly_audit",
        lane=str(result.get("lane") or "escalate30b"),
        classify_only=classify_only,
        db_path=db_path,
    )

    if not classify_only and result.get("insight"):
        insight_widget = result.get("insightWidget") or insight_widget

    return {
        "ok": bool(result.get("ok")),
        "phase": "U0",
        "kind": "monthly_audit",
        "lane": result.get("lane"),
        "classifyOnly": classify_only,
        "period": period_n,
        "snapshot": snapshot,
        "gapInsight": gap_result,
        "insightWidget": insight_widget,
        "orchestrator": {
            "ok": result.get("ok"),
            "lane": result.get("lane"),
            "structured": result.get("structured"),
            "insightError": result.get("insightError"),
        },
        "logPath": log_path,
        "refreshedAt": _utc_now(),
    }


def forecast_next_quarter(
    *,
    period: str | None = None,
    classify_only: bool = False,
    force_orchestrator: bool | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Quarter outlook — historical trend from unified DB; future points null unless 30B."""
    if not deep_audit_enabled():
        return {
            "ok": False,
            "reason": "deep_audit_disabled",
            "phase": "U0",
            "refreshedAt": _utc_now(),
        }

    snapshot = build_audit_snapshot(period=period, db_path=db_path, limit=6)
    period_n = str(snapshot.get("period"))

    try:
        from apex_orchestrator_pack import orchestrate, orchestrator_enabled
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"orchestrator_import:{exc}", "phase": "U0"}

    enabled = orchestrator_enabled() if force_orchestrator is None else bool(force_orchestrator)
    if not enabled:
        return {
            "ok": False,
            "reason": "orchestrator_disabled",
            "phase": "U0",
            "snapshot": snapshot,
            "refreshedAt": _utc_now(),
        }

    # Always publish honest historical+null-forecast scaffold (no invented $)
    trend = build_historical_trend_insight(snapshot)
    insight_widget = _publish_insight(trend)

    query = (
        f"Forecast next quarter production and payroll-to-production outlook "
        f"from unified DB starting {period_n}"
    )
    result = orchestrate(
        query,
        classify_only=classify_only,
        force_enabled=True,
        require_structured=True,
        system_prompt=FORECAST_SYSTEM_PROMPT,
        context={"deepForecast": snapshot, "period": period_n},
    )

    log_path = _persist_audit_log(
        kind="quarter_forecast",
        lane=str(result.get("lane") or "escalate30b"),
        classify_only=classify_only,
        db_path=db_path,
    )

    if not classify_only and result.get("insight"):
        insight_widget = result.get("insightWidget") or insight_widget

    return {
        "ok": bool(result.get("ok")),
        "phase": "U0",
        "kind": "quarter_forecast",
        "lane": result.get("lane"),
        "classifyOnly": classify_only,
        "period": period_n,
        "snapshot": snapshot,
        "trendInsight": trend,
        "insightWidget": insight_widget,
        "orchestrator": {
            "ok": result.get("ok"),
            "lane": result.get("lane"),
            "structured": result.get("structured"),
            "insightError": result.get("insightError"),
        },
        "logPath": log_path,
        "refreshedAt": _utc_now(),
    }


def deep_audit_status() -> dict[str, Any]:
    from apex_orchestrator_pack import orchestrator_enabled

    return {
        "ok": True,
        "phase": "U0",
        "deepAuditEnabled": deep_audit_enabled(),
        "orchestratorEnabled": orchestrator_enabled(),
        "flag": "NR2_DEEP_AUDIT",
        "endpoints": {
            "audit": "POST /api/apex/hal/deep-audit",
            "forecast": "POST /api/apex/hal/deep-forecast",
            "status": "GET /api/apex/hal/deep-audit-status",
        },
        "cli": "python scripts/run_nr2_deep_audit.py [--classify-only] [--forecast]",
        "note": "On-demand + Task Scheduler; classify_only never calls Ollama.",
        "refreshedAt": _utc_now(),
    }


def deep_audit_widget(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    del bundle
    st = deep_audit_status()
    snap = build_audit_snapshot(limit=3)
    if snap.get("dataPending"):
        return {
            "id": "deep-audit-status",
            "type": "status",
            "label": "Deep Audit (U0)",
            "size": "full",
            "status": "empty",
            "message": "Audit data pending",
            "emptyMessage": "Import SoftDent production + QB payroll/P&L, Sync, then run deep audit.",
            "hint": "Gap codes when empty — never $0. CLI: run_nr2_deep_audit.py --classify-only",
            "gapCodes": snap.get("gapCodes"),
        }
    latest = (snap.get("productionVsPayroll") or [{}])[0]
    return {
        "id": "deep-audit-status",
        "type": "status",
        "label": "Deep Audit (U0)",
        "size": "full",
        "status": "ok",
        "message": (
            f"Ready · period={snap.get('period')} · "
            f"prod rows={len(snap.get('productionVsPayroll') or [])} · "
            f"flag={'ON' if st.get('deepAuditEnabled') else 'OFF'}"
        ),
        "hint": f"Latest prod={latest.get('totalProduction')} payroll={latest.get('totalPayroll')}",
        "period": snap.get("period"),
    }
