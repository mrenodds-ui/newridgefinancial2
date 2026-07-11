"""
NR2 Apex — Bar/trend graphs + page org (Moonshot BAR_TREND_PAGE_ORG consult 2026-07-11).

Phases 1–6 placeable instruments. Never invents dollars. Phase 5 A/R forecast remains
honestly blocked until ERA 835 payer velocity exists.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STORE_KEY_IMPORT_TIMELINE = "nr2:v2:imports:health-timeline"
STORE_KEY_CLAIMS_AGING_TREND = "nr2:v2:claims:aging-trend"
MAX_POINTS = 60


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _store():
    from document_sync import NR2_DATA_DIR
    from local_store import LocalStore

    return LocalStore(NR2_DATA_DIR)


def _fallback_path(key: str) -> Path:
    from document_sync import NR2_DATA_DIR

    safe = re.sub(r"[^\w.\-]+", "_", key)
    path = Path(NR2_DATA_DIR) / "improve_pack"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{safe}.json"


def _load_json(key: str) -> dict[str, Any]:
    try:
        store = _store()
        raw = store.get(key)
        if not raw:
            raise RuntimeError("empty")
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            return json.loads(raw) if raw.strip() else {}
    except Exception:
        try:
            p = _fallback_path(key)
            if p.is_file():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_json(key: str, payload: dict[str, Any]) -> None:
    try:
        store = _store()
        store.set(key, json.dumps(payload))
        return
    except Exception:
        pass
    p = _fallback_path(key)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _append_point(key: str, point: dict[str, Any], *, dedupe_day: bool = True) -> list[dict[str, Any]]:
    data = _load_json(key)
    points = data.get("points") if isinstance(data.get("points"), list) else []
    day = str(point.get("at") or _utc_now())[:10]
    if dedupe_day:
        points = [
            p
            for p in points
            if not (isinstance(p, dict) and str(p.get("at") or "")[:10] == day)
        ]
    points.append(point)
    points = [p for p in points if isinstance(p, dict)][-MAX_POINTS:]
    data["points"] = points
    _save_json(key, data)
    return points


def _era_velocity_available() -> bool:
    """True only when IMP-004 ERA 835 payer-velocity series exists. Not shipped yet."""
    return False


# ——— Phase 2: Claims charts ———


def build_claims_status_bar(
    summary: dict[str, Any] | None,
    kanban_counts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """CLM-001: bar counts from kanban columns (exact card counts) or byStatus."""
    series: list[dict[str, Any]] = []
    counts = kanban_counts if isinstance(kanban_counts, dict) else {}
    # Prefer live Claims Workbench column keys (mockup parity)
    kanban_order = (
        "submitted",
        "pendingReview",
        "eraMatched",
        "denied",
        "paid",
        "open",
        "pending",
        "other",
    )
    labels = {
        "submitted": "Submitted",
        "pendingReview": "Pending Review",
        "eraMatched": "ERA Matched",
        "denied": "Denied",
        "paid": "Paid",
        "open": "Open",
        "pending": "Pending",
        "other": "Other",
    }
    if counts:
        for key in kanban_order:
            n = counts.get(key)
            if isinstance(n, int) and n > 0:
                series.append({"label": labels.get(key, key.title()), "value": float(n)})
        for key, n in counts.items():
            if key in labels:
                continue
            if isinstance(n, int) and n > 0:
                series.append({"label": str(key)[:24], "value": float(n)})
    else:
        by_status = (summary or {}).get("byStatus") if isinstance(summary, dict) else {}
        if isinstance(by_status, dict):
            for status, n in sorted(by_status.items(), key=lambda kv: int(kv[1] or 0), reverse=True)[:8]:
                if isinstance(n, int) and n > 0:
                    series.append({"label": str(status)[:24], "value": float(n)})

    if not series:
        return {
            "id": "claims-status-bar",
            "type": "chart",
            "chartType": "bar",
            "label": "Claims Status Distribution",
            "size": "m",
            "series": [],
            "status": "empty",
            "emptyMessage": "No claims status counts",
            "hint": "Import SoftDent ClaimStatus — bars mirror workbench column counts.",
            "collapseWhenEmpty": True,
            "compact": True,
        }
    return {
        "id": "claims-status-bar",
        "type": "chart",
        "chartType": "bar",
        "label": "Claims Status Distribution",
        "size": "m",
        "series": series,
        "status": "ok",
        "hint": "Bar heights match Claims Workbench column card counts (import-backed).",
    }


def build_claims_aging_mini_trend(aging_counts: dict[str, Any] | None) -> dict[str, Any]:
    """CLM-002: line of 90+ (and total aged) snapshots over visits — honest empty until ≥2 points."""
    counts = aging_counts if isinstance(aging_counts, dict) else {}
    c30 = int(counts.get("30") or 0)
    c60 = int(counts.get("60") or 0)
    c90 = int(counts.get("90") or 0)
    total_aged = c30 + c60 + c90
    if total_aged or c90:
        points = _append_point(
            STORE_KEY_CLAIMS_AGING_TREND,
            {
                "at": _utc_now(),
                "c30": c30,
                "c60": c60,
                "c90": c90,
                "totalAged": total_aged,
                "value": float(c90),
            },
        )
    else:
        data = _load_json(STORE_KEY_CLAIMS_AGING_TREND)
        points = data.get("points") if isinstance(data.get("points"), list) else []

    series = []
    for p in points:
        if not isinstance(p, dict):
            continue
        if isinstance(p.get("value"), (int, float)):
            series.append({"label": str(p.get("at") or "")[:10], "value": float(p["value"])})

    if len(series) < 2:
        return {
            "id": "claims-aging-mini-trend",
            "type": "chart",
            "chartType": "line",
            "label": "Claims 90+ Aging Trend",
            "size": "m",
            "series": series,
            "status": "empty" if not series else "ok",
            "emptyMessage": "Need 2+ daily snapshots",
            "hint": (
                f"Recorded today: 90+={c90}, aged 30+={total_aged}. "
                "Trend fills as Claims is opened on later days — not invented."
                if (total_aged or c90)
                else "Import SoftDent claims with Age/DOS. Snapshots accumulate on page load."
            ),
            "collapseWhenEmpty": len(series) == 0,
            "compact": len(series) == 0,
        }
    return {
        "id": "claims-aging-mini-trend",
        "type": "chart",
        "chartType": "line",
        "label": "Claims 90+ Aging Trend",
        "size": "m",
        "series": series[-30:],
        "status": "ok",
        "hint": "Daily snapshots of 90+ claim counts from SoftDent aging buckets.",
    }


# ——— Phase 3: Import health timeline ———


def build_import_health_timeline(bundle: dict[str, Any]) -> dict[str, Any]:
    """SD-001: connected dataset count (and stale days) over visits."""
    try:
        from apex_program_improve_pack import assess_import_health

        health = assess_import_health(bundle)
    except Exception:
        health = {}

    summary = health.get("summary") if isinstance(health.get("summary"), dict) else {}
    connected = summary.get("connected")
    total = summary.get("total")
    stale_days = health.get("staleDays")
    value = float(connected) if isinstance(connected, int) else None

    # SoftDent row signal for secondary series
    softdent = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
    row_total = 0
    for sec in softdent.values():
        if isinstance(sec, dict) and isinstance(sec.get("rows"), list):
            row_total += len(sec["rows"])
        elif isinstance(sec, list):
            row_total += len(sec)

    if value is not None:
        points = _append_point(
            STORE_KEY_IMPORT_TIMELINE,
            {
                "at": _utc_now(),
                "value": value,
                "connected": connected,
                "total": total,
                "staleDays": stale_days,
                "softdentRows": row_total,
            },
        )
    else:
        data = _load_json(STORE_KEY_IMPORT_TIMELINE)
        points = data.get("points") if isinstance(data.get("points"), list) else []

    series = []
    for p in points:
        if isinstance(p, dict) and isinstance(p.get("value"), (int, float)):
            series.append({"label": str(p.get("at") or "")[:10], "value": float(p["value"])})

    stale_alert = isinstance(stale_days, int) and stale_days >= 7
    if len(series) < 2:
        return {
            "id": "import-health-timeline",
            "type": "chart",
            "chartType": "line",
            "label": "Import Health Timeline",
            "size": "m",
            "series": series,
            "status": "empty" if not series else "ok",
            "emptyMessage": "Need 2+ daily snapshots",
            "hint": (
                f"Connected datasets now: {connected}/{total}. "
                + (
                    f"⚠ Imports last loaded {stale_days} day(s) ago — sync SoftDent/QB."
                    if stale_alert
                    else "Timeline fills as SoftDent page is opened on later days."
                )
            ),
            "alert": stale_alert,
            "collapseWhenEmpty": len(series) == 0,
            "compact": len(series) == 0,
        }
    out = {
        "id": "import-health-timeline",
        "type": "chart",
        "chartType": "line",
        "label": "Import Health Timeline",
        "size": "m",
        "series": series[-30:],
        "status": "ok",
        "hint": "Connected import datasets over time (diagnostics). Not dollar amounts.",
        "alert": stale_alert,
    }
    if stale_alert:
        out["alertReason"] = f"Imports last loaded {stale_days} day(s) ago"
    return out


def build_stale_import_alert_chip(bundle: dict[str, Any]) -> dict[str, Any]:
    """Strip chip when imports older than 7 days."""
    try:
        from apex_program_improve_pack import assess_import_health

        health = assess_import_health(bundle)
    except Exception:
        health = {}
    stale_days = health.get("staleDays")
    if isinstance(stale_days, int) and stale_days >= 7:
        return {
            "id": "stale-import-alert",
            "type": "status",
            "label": "Import Stale Alert",
            "size": "strip",
            "compact": True,
            "status": "empty",
            "message": f"Imports {stale_days}d old",
            "hint": "Sync SoftDent Register/Daysheet and QuickBooks P&L (weekly export task).",
            "alert": True,
            "alertReason": f"loadedAt age {stale_days} days ≥ 7",
        }
    return {
        "id": "stale-import-alert",
        "type": "status",
        "label": "Import Stale Alert",
        "size": "strip",
        "compact": True,
        "status": "ok",
        "message": "Fresh enough",
        "hint": (
            f"Last load age: {stale_days} day(s)."
            if isinstance(stale_days, int)
            else "Import age unknown until bundle loadedAt is present."
        ),
        "collapseWhenEmpty": False,
    }


# ——— Phase 4: Operatory utilization ———


def build_operatory_util_chart(bundle: dict[str, Any]) -> dict[str, Any]:
    """OM-001: bars of scheduled slots per chair (import-backed; not invented %)."""
    softdent = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
    chairs: list[Any] = []
    for key in ("operatory", "operatorySchedule", "schedule"):
        sec = softdent.get(key)
        if isinstance(sec, dict) and isinstance(sec.get("operatoryChairs"), list):
            chairs = sec["operatoryChairs"]
            break
    series: list[dict[str, Any]] = []
    for chair in chairs:
        if not isinstance(chair, dict):
            continue
        name = str(chair.get("name") or chair.get("operatory") or chair.get("id") or "Chair")[:28]
        slots = chair.get("slots") if isinstance(chair.get("slots"), list) else []
        series.append({"label": name, "value": float(len(slots))})
    series = sorted(series, key=lambda s: s["value"], reverse=True)[:12]
    if not series:
        return {
            "id": "operatory-util-trend",
            "type": "chart",
            "chartType": "bar",
            "label": "Operatory Slot Load",
            "size": "m",
            "series": [],
            "status": "empty",
            "emptyMessage": "No operatory schedule",
            "hint": "Need SoftDent operatory_schedule.json with operatoryChairs[].slots.",
            "collapseWhenEmpty": True,
            "compact": True,
        }
    return {
        "id": "operatory-util-trend",
        "type": "chart",
        "chartType": "bar",
        "label": "Operatory Slot Load",
        "size": "m",
        "series": series,
        "status": "ok",
        "hint": "Scheduled slot counts per chair from SoftDent operatory import (not capacity %).",
    }


# ——— Phase 5: A/R forecast blocked stub ———


def build_ar_forecast_trend_blocked(reports: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    """AR-001: dual-axis A/R forecast stays empty until ERA 835 payer velocity (IMP-004)."""
    del reports, bundle
    if _era_velocity_available():
        # Reserved for future ERA velocity series — never synthesize.
        pass
    return {
        "id": "ar-forecast-trend",
        "type": "dual-axis-trend",
        "label": "A/R Forecast (ERA Velocity)",
        "size": "strip",
        "compact": True,
        "collapseWhenEmpty": True,
        "production": [],
        "collections": [],
        "status": "empty",
        "emptyMessage": "Blocked — needs ERA 835",
        "hint": (
            "Moonshot Phase 5: dual-axis A/R forecast requires ERA 835 payer velocity "
            "(IMP-004). No illustrative decay dollars shown. Use A/R Aging + Collection Efficiency until then."
        ),
        "blocked": True,
        "blockedReason": "IMP-004 ERA 835 parser",
    }


# ——— Phase 1 / FIN-004: EBITDA variance ———


def build_ebitda_variance_bar(bundle: dict[str, Any]) -> dict[str, Any]:
    """FIN-004: bar of period-over-period EBITDA deltas from accumulated snapshots / QB P&L."""
    series: list[dict[str, Any]] = []
    try:
        from apex_program_improve_pack import STORE_KEY_EBITDA_TREND, build_ebitda_trend_widget

        build_ebitda_trend_widget(bundle)
        data = _load_json(STORE_KEY_EBITDA_TREND)
        points = data.get("points") if isinstance(data.get("points"), list) else []
        vals = [
            (str(p.get("label") or p.get("at") or "")[:10], float(p["value"]))
            for p in points
            if isinstance(p, dict) and isinstance(p.get("value"), (int, float))
        ]
        for i in range(1, len(vals)):
            prev_lab, prev_v = vals[i - 1]
            lab, v = vals[i]
            series.append({"label": lab or prev_lab, "value": round(v - prev_v, 2)})
    except Exception:
        series = []

    # Fallback: consecutive QB P&L NetIncome periods
    if len(series) < 1:
        try:
            from apex_backend import _qb_pick, _section_rows

            pl_rows = _section_rows(bundle, "quickbooks", "profitAndLoss")
            dated: list[tuple[str, float]] = []
            for row in pl_rows if isinstance(pl_rows, list) else []:
                if not isinstance(row, dict):
                    continue
                net = _qb_pick(row, ("NetIncome", "net_income", "Net Income"))
                if net is None:
                    continue
                lab = str(row.get("Period") or row.get("period") or "")[:10]
                dated.append((lab or "period", float(net)))
            for i in range(1, len(dated)):
                series.append({"label": dated[i][0], "value": round(dated[i][1] - dated[i - 1][1], 2)})
        except Exception:
            pass

    if len(series) < 1:
        return {
            "id": "ebitda-variance-bar",
            "type": "chart",
            "chartType": "bar",
            "label": "EBITDA / Net Income Variance",
            "size": "strip",
            "compact": True,
            "collapseWhenEmpty": True,
            "series": [],
            "status": "empty",
            "emptyMessage": "Need 2+ periods",
            "hint": "Import 2+ QuickBooks P&L periods (or revisit Financial so EBITDA snapshots accumulate).",
        }
    return {
        "id": "ebitda-variance-bar",
        "type": "chart",
        "chartType": "bar",
        "label": "EBITDA / Net Income Variance",
        "size": "m",
        "series": series[-12:],
        "status": "ok",
        "hint": "Period-over-period change from import-backed snapshots / QB Net Income — not invented.",
    }
