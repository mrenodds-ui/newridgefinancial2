"""
Phase U2 — Reconciliation engine (Moonshot REAUDIT3 SHOULD).
Phase V2 — Optional 30B explanation LRU cache (Moonshot REAUDIT4 NICE).

Detect SoftDent×QB variances from v_production_vs_payroll / v_collection_vs_ap.
Default thresholds: 5% or $500 (overridable via env). Optional 30B explainer.
Honesty: never invent dollars; gap codes when views empty. No SoftDent write-back.
Flag: NR2_RECONCILIATION (default ON).
Flag: NR2_EXPLAIN_CACHE (default OFF until burn-in — invalidate on import).
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GAP_RECON_PENDING = "RECON_DATA_PENDING"
GAP_RECON_VARIANCE = "RECON_VARIANCE"

DEFAULT_VARIANCE_PCT = 0.05
DEFAULT_VARIANCE_ABS = 500.0
EXPLAIN_CACHE_MAXSIZE = 128

EXPLAIN_SYSTEM = (
    "You are a dental practice CFO AI. Explain the SoftDent vs QuickBooks variance "
    "using ONLY the provided mirrored numbers and source_refs. Output ONLY JSON "
    "widget_type='alert-banner' with data.value null or the provided delta, "
    "confidence, and source_refs. Never invent dollars. No PHI. No prose outside JSON."
)

# V2 — period+delta_hash LRU; cleared on import completion (generation bump + clear).
_EXPLAIN_CACHE: OrderedDict[tuple[Any, ...], dict[str, Any]] = OrderedDict()
_EXPLAIN_CACHE_GEN = 0
_EXPLAIN_CACHE_HITS = 0
_EXPLAIN_CACHE_MISSES = 0


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def reconciliation_enabled() -> bool:
    raw = str(os.getenv("NR2_RECONCILIATION") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def explain_cache_enabled() -> bool:
    """V2 — 30B variance explainer LRU. Default OFF until burn-in."""
    raw = str(os.getenv("NR2_EXPLAIN_CACHE") or "0").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def variance_delta_hash(finding: dict[str, Any]) -> str:
    """Stable hash of mirrored variance fields used as explain cache key."""
    payload = {
        "kind": finding.get("kind"),
        "period": finding.get("period"),
        "gapCode": finding.get("gapCode"),
        "reasons": finding.get("reasons"),
        "deltas": finding.get("deltas"),
        "thresholds": finding.get("thresholds"),
        "production": finding.get("production"),
        "payroll": finding.get("payroll"),
        "ratio": finding.get("ratio"),
        "collections": finding.get("collections"),
        "totalAp": finding.get("totalAp"),
        "netProfit": finding.get("netProfit"),
    }
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def invalidate_explain_cache(*, reason: str = "import") -> dict[str, Any]:
    """Clear 30B explanation cache (call on any import completion)."""
    global _EXPLAIN_CACHE_GEN, _EXPLAIN_CACHE_HITS, _EXPLAIN_CACHE_MISSES
    _EXPLAIN_CACHE.clear()
    _EXPLAIN_CACHE_GEN += 1
    _EXPLAIN_CACHE_HITS = 0
    _EXPLAIN_CACHE_MISSES = 0
    return {
        "ok": True,
        "phase": "V2",
        "reason": str(reason or "import"),
        "generation": _EXPLAIN_CACHE_GEN,
        "size": 0,
    }


def explain_cache_stats() -> dict[str, Any]:
    return {
        "enabled": explain_cache_enabled(),
        "flag": "NR2_EXPLAIN_CACHE",
        "generation": _EXPLAIN_CACHE_GEN,
        "size": len(_EXPLAIN_CACHE),
        "maxsize": EXPLAIN_CACHE_MAXSIZE,
        "hits": _EXPLAIN_CACHE_HITS,
        "misses": _EXPLAIN_CACHE_MISSES,
    }


def explain_variance(
    finding: dict[str, Any],
    *,
    classify_only: bool = False,
    force_orchestrator: bool | None = None,
) -> dict[str, Any]:
    """
    Optional 30B (orchestrator) explanation for a variance finding.
    Cache key: (period, delta_hash, classify_only, force) when NR2_EXPLAIN_CACHE=1.
    """
    global _EXPLAIN_CACHE_HITS, _EXPLAIN_CACHE_MISSES

    period = _normalize_period(str(finding.get("period") or ""))
    delta_hash = variance_delta_hash(finding)
    force_flag = None if force_orchestrator is None else bool(force_orchestrator)
    cache_key = (period, delta_hash, bool(classify_only), force_flag, _EXPLAIN_CACHE_GEN)

    if explain_cache_enabled() and cache_key in _EXPLAIN_CACHE:
        _EXPLAIN_CACHE.move_to_end(cache_key)
        _EXPLAIN_CACHE_HITS += 1
        hit = copy.deepcopy(_EXPLAIN_CACHE[cache_key])
        hit["cacheHit"] = True
        hit["period"] = period
        hit["deltaHash"] = delta_hash
        hit["cacheGeneration"] = _EXPLAIN_CACHE_GEN
        return hit

    if explain_cache_enabled():
        _EXPLAIN_CACHE_MISSES += 1

    try:
        from apex_orchestrator_pack import orchestrate, orchestrator_enabled

        enabled = orchestrator_enabled() if force_orchestrator is None else bool(force_orchestrator)
        if not enabled:
            result: dict[str, Any] = {
                "ok": False,
                "reason": "orchestrator_disabled",
                "cacheHit": False,
                "period": period,
                "deltaHash": delta_hash,
            }
        else:
            query = (
                f"Explain SoftDent vs QuickBooks reconciliation variance for {finding.get('period')} "
                f"kind={finding.get('kind')} reasons={finding.get('reasons')} "
                f"deltas={finding.get('deltas')} thresholds={finding.get('thresholds')}. "
                "Output structured alert-banner JSON only."
            )
            result = orchestrate(
                query,
                classify_only=classify_only,
                force_enabled=True,
                require_structured=True,
                system_prompt=EXPLAIN_SYSTEM,
                context={"reconciliation": {"findings": [finding]}},
            )
            if not isinstance(result, dict):
                result = {"ok": False, "error": "orchestrator_non_dict"}
            result = dict(result)
            result["cacheHit"] = False
            result["period"] = period
            result["deltaHash"] = delta_hash
    except Exception as exc:  # noqa: BLE001
        result = {
            "ok": False,
            "error": str(exc),
            "cacheHit": False,
            "period": period,
            "deltaHash": delta_hash,
        }

    if explain_cache_enabled() and result.get("ok"):
        _EXPLAIN_CACHE[cache_key] = copy.deepcopy(result)
        _EXPLAIN_CACHE.move_to_end(cache_key)
        while len(_EXPLAIN_CACHE) > EXPLAIN_CACHE_MAXSIZE:
            _EXPLAIN_CACHE.popitem(last=False)
        result["cacheGeneration"] = _EXPLAIN_CACHE_GEN

    return result


def variance_threshold_pct() -> float:
    raw = str(os.getenv("NR2_VARIANCE_PCT") or "").strip()
    if not raw:
        return DEFAULT_VARIANCE_PCT
    try:
        v = float(raw)
        # allow "5" meaning 5% or "0.05"
        return v / 100.0 if v > 1 else v
    except ValueError:
        return DEFAULT_VARIANCE_PCT


def variance_threshold_abs() -> float:
    raw = str(os.getenv("NR2_VARIANCE_ABS") or "").strip()
    try:
        return float(raw) if raw else DEFAULT_VARIANCE_ABS
    except ValueError:
        return DEFAULT_VARIANCE_ABS


def _normalize_period(period: str | None) -> str:
    raw = str(period or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}", raw):
        return raw
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _prior_period(period: str) -> str:
    y, m = int(period[:4]), int(period[5:7])
    m -= 1
    if m <= 0:
        m = 12
        y -= 1
    return f"{y:04d}-{m:02d}"


def _f(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _exceeds(delta_abs: float | None, base: float | None, *, pct: float, abs_th: float) -> bool:
    if delta_abs is None:
        return False
    if abs(delta_abs) >= abs_th:
        return True
    if base is not None and abs(base) > 0 and abs(delta_abs) / abs(base) >= pct:
        return True
    return False


def check_production_payroll_variance(
    period: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    """
    MoM variance on production and payroll-to-production ratio.
    Also flags production present with missing payroll (gap — not $0).
    """
    from apex_unified_db_pack import list_production_vs_payroll

    period = _normalize_period(period)
    prior = _prior_period(period)
    rows = list_production_vs_payroll(limit=24, db_path=db_path)
    by_p = {str(r.get("period")): r for r in rows if isinstance(r, dict)}
    cur = by_p.get(period)
    if not cur:
        # try latest if exact period missing
        if rows:
            cur = rows[0]
            period = str(cur.get("period") or period)
            prior = _prior_period(period)
        else:
            return {
                "ok": True,
                "alert": False,
                "gapCode": GAP_RECON_PENDING,
                "period": period,
                "kind": "production_vs_payroll",
                "fixHint": "Import SoftDent production + QB payroll, then Sync. Empty ≠ $0.",
            }

    prod = _f(cur.get("totalProduction"))
    payroll = _f(cur.get("totalPayroll"))
    ratio = _f(cur.get("payrollToProductionRatio"))
    prev = by_p.get(prior)

    pct = variance_threshold_pct()
    abs_th = variance_threshold_abs()
    reasons: list[str] = []
    deltas: dict[str, Any] = {}

    if prod is not None and (payroll is None or payroll == 0):
        reasons.append("payroll_missing_while_production_present")
        return {
            "ok": True,
            "alert": True,
            "gapCode": "RECON_PAYROLL_PENDING",
            "period": period,
            "kind": "production_vs_payroll",
            "production": prod,
            "payroll": None,
            "ratio": ratio,
            "reasons": reasons,
            "thresholds": {"pct": pct, "abs": abs_th},
            "fixHint": "QB payroll export missing for period — empty ≠ $0.",
            "source_refs": [f"nr2:v_production_vs_payroll:{period}"],
        }

    if prev:
        prev_prod = _f(prev.get("totalProduction"))
        prev_payroll = _f(prev.get("totalPayroll"))
        prev_ratio = _f(prev.get("payrollToProductionRatio"))
        if prod is not None and prev_prod is not None:
            d_prod = prod - prev_prod
            deltas["productionDelta"] = d_prod
            if _exceeds(d_prod, prev_prod, pct=pct, abs_th=abs_th):
                reasons.append("production_mom_variance")
        if payroll is not None and prev_payroll is not None:
            d_pay = payroll - prev_payroll
            deltas["payrollDelta"] = d_pay
            if _exceeds(d_pay, prev_payroll, pct=pct, abs_th=abs_th):
                reasons.append("payroll_mom_variance")
        if ratio is not None and prev_ratio is not None:
            d_ratio = ratio - prev_ratio
            deltas["ratioDelta"] = d_ratio
            if abs(d_ratio) >= pct:
                reasons.append("payroll_to_production_ratio_mom")

    # Same-period SoftDent vs QB structural gap: production without joinable payroll already handled;
    # large payroll share of production (>50%) as operational alert (not inventing $)
    if ratio is not None and ratio >= 0.5:
        reasons.append("payroll_share_ge_50pct")

    if not reasons:
        return {
            "ok": True,
            "alert": False,
            "period": period,
            "priorPeriod": prior if prev else None,
            "kind": "production_vs_payroll",
            "production": prod,
            "payroll": payroll,
            "ratio": ratio,
            "deltas": deltas,
            "thresholds": {"pct": pct, "abs": abs_th},
        }

    return {
        "ok": True,
        "alert": True,
        "gapCode": GAP_RECON_VARIANCE,
        "period": period,
        "priorPeriod": prior if prev else None,
        "kind": "production_vs_payroll",
        "production": prod,
        "payroll": payroll,
        "ratio": ratio,
        "deltas": deltas,
        "reasons": reasons,
        "thresholds": {"pct": pct, "abs": abs_th},
        "source_refs": [
            f"nr2:v_production_vs_payroll:{period}",
            f"softdent:production:{period}",
            f"qb:payroll:{period}",
        ],
    }


def check_collection_ap_variance(
    period: str,
    *,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    from apex_unified_db_pack import list_collection_vs_ap

    period = _normalize_period(period)
    prior = _prior_period(period)
    rows = list_collection_vs_ap(limit=24, db_path=db_path)
    by_p = {str(r.get("period")): r for r in rows if isinstance(r, dict)}
    cur = by_p.get(period)
    if not cur:
        if rows:
            cur = rows[0]
            period = str(cur.get("period") or period)
            prior = _prior_period(period)
        else:
            return {
                "ok": True,
                "alert": False,
                "gapCode": GAP_RECON_PENDING,
                "period": period,
                "kind": "collection_vs_ap",
                "fixHint": "Import SoftDent collections + QB AP, then Sync. Empty ≠ $0.",
            }

    coll = _f(cur.get("collections"))
    ap = _f(cur.get("totalAp"))
    net = _f(cur.get("netProfit"))
    prev = by_p.get(prior)
    pct = variance_threshold_pct()
    abs_th = variance_threshold_abs()
    reasons: list[str] = []
    deltas: dict[str, Any] = {}

    if coll is None and ap is not None:
        reasons.append("collections_missing_while_ap_present")
        return {
            "ok": True,
            "alert": True,
            "gapCode": "RECON_COLLECTIONS_PENDING",
            "period": period,
            "kind": "collection_vs_ap",
            "collections": None,
            "totalAp": ap,
            "netProfit": net,
            "reasons": reasons,
            "fixHint": "SoftDent collections pending — empty ≠ $0; never post from AP.",
            "source_refs": [f"nr2:v_collection_vs_ap:{period}"],
        }

    if prev:
        prev_coll = _f(prev.get("collections"))
        prev_ap = _f(prev.get("totalAp"))
        if coll is not None and prev_coll is not None:
            d = coll - prev_coll
            deltas["collectionsDelta"] = d
            if _exceeds(d, prev_coll, pct=pct, abs_th=abs_th):
                reasons.append("collections_mom_variance")
        if ap is not None and prev_ap is not None:
            d = ap - prev_ap
            deltas["apDelta"] = d
            if _exceeds(d, prev_ap, pct=pct, abs_th=abs_th):
                reasons.append("ap_mom_variance")

    if coll is not None and ap is not None and coll > 0 and ap / coll >= 0.5:
        reasons.append("ap_share_of_collections_ge_50pct")

    if not reasons:
        return {
            "ok": True,
            "alert": False,
            "period": period,
            "kind": "collection_vs_ap",
            "collections": coll,
            "totalAp": ap,
            "netProfit": net,
            "deltas": deltas,
            "thresholds": {"pct": pct, "abs": abs_th},
        }

    return {
        "ok": True,
        "alert": True,
        "gapCode": GAP_RECON_VARIANCE,
        "period": period,
        "kind": "collection_vs_ap",
        "collections": coll,
        "totalAp": ap,
        "netProfit": net,
        "deltas": deltas,
        "reasons": reasons,
        "thresholds": {"pct": pct, "abs": abs_th},
        "source_refs": [
            f"nr2:v_collection_vs_ap:{period}",
            f"softdent:collections:{period}",
            f"qb:ap:{period}",
        ],
    }


def build_variance_insight(finding: dict[str, Any]) -> dict[str, Any]:
    """Schema-validated alert-banner from a variance finding (no invented $)."""
    period = str(finding.get("period") or _normalize_period(None))
    reasons = finding.get("reasons") or [finding.get("gapCode") or "variance"]
    msg = (
        f"{finding.get('kind')} {period}: "
        + ", ".join(str(r) for r in reasons)[:280]
        + f" (thr {finding.get('thresholds') or {}}). Empty ≠ $0."
    )
    deltas = finding.get("deltas") if isinstance(finding.get("deltas"), dict) else {}
    value: float | None = None
    unit = "text"
    if isinstance(deltas.get("productionDelta"), (int, float)):
        value = float(deltas["productionDelta"])
        unit = "dollars"
    elif isinstance(deltas.get("collectionsDelta"), (int, float)):
        value = float(deltas["collectionsDelta"])
        unit = "dollars"
    elif isinstance(deltas.get("payrollDelta"), (int, float)):
        value = float(deltas["payrollDelta"])
        unit = "dollars"
    elif isinstance(deltas.get("apDelta"), (int, float)):
        value = float(deltas["apDelta"])
        unit = "dollars"
    elif isinstance(deltas.get("ratioDelta"), (int, float)):
        value = float(deltas["ratioDelta"])
        unit = "percent"

    refs = finding.get("source_refs") if isinstance(finding.get("source_refs"), list) else []
    if not refs:
        refs = [f"nr2:unified:{period}"]
    payload = {
        "widget_type": "alert-banner",
        "title": f"Reconciliation — {period}",
        "data": {
            "severity": "warn" if finding.get("alert") else "info",
            "message": msg[:400],
            "value": value,
            "unit": unit,
        },
        "source_refs": [str(r) for r in refs][:12],
        "confidence": "medium" if value is not None else "low",
        "explanation": "U2 variance from unified views — mirrored imports only; no SoftDent write-back.",
        "action_cta": {"label": "Open Financial", "route": "financial"},
    }
    from apex_structured_insight_pack import validate_insight

    return validate_insight(payload)


def _publish(validated: dict[str, Any]) -> dict[str, Any] | None:
    if not validated.get("ok") or not isinstance(validated.get("insight"), dict):
        return None
    try:
        from apex_structured_insight_pack import ai_insight_widget, save_last_insight

        save_last_insight(validated["insight"])
        return ai_insight_widget(validated["insight"])
    except Exception:
        return None


def run_reconciliation(
    *,
    period: str | None = None,
    classify_only: bool = False,
    force_orchestrator: bool | None = None,
    db_path: Path | None = None,
    explain: bool = True,
) -> dict[str, Any]:
    """Scan production×payroll and collection×AP; emit alerts + optional 30B explain."""
    if not reconciliation_enabled():
        return {
            "ok": False,
            "reason": "reconciliation_disabled",
            "hint": "Set NR2_RECONCILIATION=1 (default on).",
            "phase": "U2",
            "refreshedAt": _utc_now(),
        }

    period_n = _normalize_period(period)
    findings = [
        check_production_payroll_variance(period_n, db_path=db_path),
        check_collection_ap_variance(period_n, db_path=db_path),
    ]
    findings = [f for f in findings if isinstance(f, dict)]
    alerts = [f for f in findings if f.get("alert")]

    insight_widget = None
    gap_insights: list[dict[str, Any]] = []
    for finding in alerts:
        validated = build_variance_insight(finding)
        gap_insights.append(validated)
        if validated.get("ok"):
            insight_widget = _publish(validated) or insight_widget

    orchestrator_result = None
    if explain and alerts:
        top = alerts[0]
        orchestrator_result = explain_variance(
            top,
            classify_only=classify_only,
            force_orchestrator=force_orchestrator,
        )
        if (
            isinstance(orchestrator_result, dict)
            and not classify_only
            and orchestrator_result.get("insightWidget")
        ):
            insight_widget = orchestrator_result.get("insightWidget")

    # Persist lightweight log
    try:
        from apex_unified_db_pack import open_unified

        flags = json.dumps(
            {
                "phase": "U2",
                "alerts": len(alerts),
                "period": period_n,
                "classify_only": classify_only,
            }
        )
        with open_unified(path=db_path) as conn:
            conn.execute(
                """
                INSERT INTO import_health_log
                    (source, export_type, row_count, staleness_hours, gap_flags, detected_at)
                VALUES (?,?,?,?,?,?)
                """,
                ("reconciliation", "variance_scan", len(alerts), None, flags, _utc_now()),
            )
            conn.commit()
    except Exception:
        pass

    return {
        "ok": True,
        "phase": "U2",
        "period": period_n,
        "alertCount": len(alerts),
        "findings": findings,
        "alerts": alerts,
        "gapInsights": gap_insights,
        "insightWidget": insight_widget,
        "orchestrator": orchestrator_result,
        "thresholds": {
            "pct": variance_threshold_pct(),
            "abs": variance_threshold_abs(),
        },
        "classifyOnly": classify_only,
        "softDentWriteBack": False,
        "refreshedAt": _utc_now(),
    }


def reconciliation_status() -> dict[str, Any]:
    return {
        "ok": True,
        "phase": "U2",
        "enabled": reconciliation_enabled(),
        "flag": "NR2_RECONCILIATION",
        "thresholds": {
            "pct": variance_threshold_pct(),
            "abs": variance_threshold_abs(),
            "envPct": "NR2_VARIANCE_PCT",
            "envAbs": "NR2_VARIANCE_ABS",
        },
        "explainCache": explain_cache_stats(),
        "endpoints": {
            "run": "POST /api/apex/hal/reconciliation",
            "status": "GET /api/apex/hal/reconciliation-status",
        },
        "cli": "python scripts/run_nr2_reconciliation.py [--classify-only] [--period YYYY-MM]",
        "refreshedAt": _utc_now(),
    }


def reconciliation_widget(bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    del bundle
    st = reconciliation_status()
    scan = run_reconciliation(classify_only=True, explain=False)
    if scan.get("reason") == "reconciliation_disabled":
        return {
            "id": "reconciliation-status",
            "type": "status",
            "label": "Reconciliation (U2)",
            "size": "full",
            "status": "empty",
            "message": "Reconciliation disabled",
            "hint": "Set NR2_RECONCILIATION=1",
        }
    alerts = int(scan.get("alertCount") or 0)
    pending = any(
        (f or {}).get("gapCode") == GAP_RECON_PENDING for f in (scan.get("findings") or [])
    )
    if pending and alerts == 0:
        return {
            "id": "reconciliation-status",
            "type": "status",
            "label": "Reconciliation (U2)",
            "size": "full",
            "status": "empty",
            "message": GAP_RECON_PENDING,
            "emptyMessage": "No SoftDent×QB join rows yet — empty ≠ $0.",
            "hint": f"Thresholds {st['thresholds']['pct']:.0%} / ${st['thresholds']['abs']:.0f}",
        }
    return {
        "id": "reconciliation-status",
        "type": "status",
        "label": "Reconciliation (U2)",
        "size": "full",
        "status": "ok" if alerts == 0 else "warn",
        "message": f"{alerts} alert(s) · period={scan.get('period')}",
        "hint": f"MoM variance gates {st['thresholds']['pct']:.0%} / ${st['thresholds']['abs']:.0f}",
        "alertCount": alerts,
    }
