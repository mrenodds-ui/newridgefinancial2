"""NR2 cross-analytics — production reconciliation, collection lag, revenue & daily production."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from import_loader import load_import_bundle, softdent_import_dir

_BUCKET_MID_DAYS = {"0-30": 15, "31-60": 45, "61-90": 75, "90+": 105, "91+": 105, "120+": 120}


def _parse_money(value: Any) -> float:
    raw = str(value or "").replace("$", "").replace(",", "").strip()
    if not raw or raw in {"—", "-", "N/A"}:
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _normalize_period(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    match = re.match(r"^(\d{4})-(\d{2})", text)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    match = re.match(r"^(\d{4})[-/](\d{1,2})$", text)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}"
    return text[:7]


def _current_month_period() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


def _period_incomplete(row: dict[str, Any]) -> bool:
    if not row:
        return False
    if row.get("collectionsPending") is True:
        return True
    if row.get("collectionsReported") is False:
        return True
    # Current calendar month with production but no reported collections is still open.
    if (
        row.get("period") == _current_month_period()
        and (row.get("production") or 0) > 0
        and not ((row.get("collections") or 0) > 0)
    ):
        return True
    return False


def _dashboard_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    dashboard = ((bundle.get("softdent") or {}).get("dashboard")) or {}
    rows: list[dict[str, Any]] = []
    if isinstance(dashboard, list):
        rows = [row for row in dashboard if isinstance(row, dict)]
    elif isinstance(dashboard, dict):
        raw = dashboard.get("rows")
        if isinstance(raw, list):
            rows = [row for row in raw if isinstance(row, dict)]
    normalized: list[dict[str, Any]] = []
    for row in rows:
        period = _normalize_period(row.get("period") or row.get("Period") or row.get("year_month"))
        if not period:
            continue
        collections_pending = row.get("collectionsPending") is True or row.get("CollectionsPending") is True
        collections_reported = False if collections_pending else row.get("collectionsReported") is not False
        normalized.append(
            {
                "period": period,
                "production": _parse_money(row.get("production") or row.get("Production")),
                "collections": _parse_money(row.get("collections") or row.get("Collections")),
                "collectionsPending": collections_pending,
                "collectionsReported": collections_reported,
            }
        )
    normalized.sort(key=lambda item: item["period"])
    return normalized


def _qb_monthly_rows(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    qb = bundle.get("quickbooks") or {}
    pl = qb.get("profitAndLoss") or {}
    revenue = qb.get("revenue") or {}
    source_rows = (pl.get("rows") if isinstance(pl, dict) else None) or (revenue.get("rows") if isinstance(revenue, dict) else None) or []
    by_period: dict[str, dict[str, Any]] = {}
    for row in source_rows:
        if not isinstance(row, dict):
            continue
        period = _normalize_period(row.get("Period") or row.get("period") or row.get("Month") or row.get("month"))
        if not period:
            continue
        income = _parse_money(
            row.get("TotalIncome") or row.get("Income") or row.get("Revenue") or row.get("total_income") or row.get("Amount")
        )
        if income <= 0:
            continue
        by_period[period] = {"period": period, "revenue": income}
    monthly = list(by_period.values())
    monthly.sort(key=lambda item: item["period"])
    return monthly


def _ar_weighted_dso(ar_rows: list[dict[str, Any]]) -> float | None:
    if not ar_rows:
        return None
    weighted = 0.0
    total = 0.0
    for row in ar_rows:
        amount = _parse_money(row.get("Balance") or row.get("Outstanding") or row.get("Amount") or row.get("Total"))
        if amount <= 0:
            continue
        bucket = str(row.get("Aging") or row.get("Bucket") or row.get("AgeBucket") or row.get("bucket") or "")
        days = None
        for key, mid in _BUCKET_MID_DAYS.items():
            if key in bucket:
                days = mid
                break
        if days is None:
            match = re.search(r"(\d+)", str(row.get("Days") or row.get("AgeDays") or ""))
            days = float(match.group(1)) if match else 45.0
        weighted += amount * days
        total += amount
    if total <= 0:
        return None
    return round(weighted / total, 1)


def _sd_procedures_daily(limit: int = 30) -> list[dict[str, Any]]:
    try:
        from softdent_odbc_extract import resolve_sd_sqlite_db, table_row_counts
    except ImportError:
        return []
    db_path = resolve_sd_sqlite_db()
    if not db_path or not db_path.is_file():
        return []
    counts = table_row_counts(db_path)
    if int(counts.get("sd_procedures") or 0) <= 0:
        return []
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT proc_date, SUM(COALESCE(production, 0))
            FROM sd_procedures
            WHERE proc_date IS NOT NULL AND proc_date != '' AND COALESCE(production, 0) > 0
            GROUP BY proc_date
            ORDER BY proc_date
            """
        )
        rows = [(str(day), float(total or 0)) for day, total in cur.fetchall() if day]
    finally:
        conn.close()
    if not rows:
        return []
    trimmed = rows[-limit:]
    return [{"date": day, "production": round(total, 2)} for day, total in trimmed]


def _daysheet_daily_production(limit: int = 30) -> list[dict[str, Any]]:
    try:
        from softdent_operational_pipeline import _load_daysheet_transactions, resolve_daysheet_jsonl_path
    except ImportError:
        return []
    path = resolve_daysheet_jsonl_path()
    if not path or not path.is_file():
        return []
    by_date: dict[str, float] = {}
    for row in _load_daysheet_transactions(path):
        report_date = str(row.get("reportDate") or "").strip()
        production = row.get("production")
        if not report_date or production in (None, "", 0):
            continue
        amount = _parse_money(production)
        if amount <= 0:
            continue
        by_date[report_date] = by_date.get(report_date, 0.0) + amount
    if not by_date:
        return []
    dates = sorted(by_date.keys())[-limit:]
    return [{"date": day, "production": round(by_date[day], 2)} for day in dates]


def production_reconciliation(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    bundle = bundle or load_import_bundle(sync=False)
    sd_rows = _dashboard_rows(bundle)
    qb_rows = _qb_monthly_rows(bundle)
    qb_by_period = {row["period"]: row["revenue"] for row in qb_rows}
    rows: list[dict[str, Any]] = []
    for sd in sd_rows:
        period = sd["period"]
        production = sd["production"]
        qb_revenue = qb_by_period.get(period)
        if production <= 0 and (qb_revenue is None or qb_revenue <= 0):
            continue
        variance_pct = None
        tone = "neutral"
        if production > 0 and qb_revenue is not None:
            variance_pct = round(((qb_revenue - production) / production) * 100, 1)
            if abs(variance_pct) <= 3:
                tone = "ok"
            elif abs(variance_pct) <= 10:
                tone = "warn"
            else:
                tone = "alert"
        rows.append(
            {
                "period": period,
                "softdentProduction": round(production, 2),
                "quickbooksRevenue": round(qb_revenue, 2) if qb_revenue is not None else None,
                "variancePct": variance_pct,
                "tone": tone,
            }
        )
    latest = rows[-1] if rows else None
    return {
        "rows": rows[-12:],
        "latest": latest,
        "summary": (
            f"Latest period {latest['period']}: {latest['variancePct']}% variance (SoftDent production vs QB revenue)."
            if latest and latest.get("variancePct") is not None
            else "Production reconciliation populates when SoftDent dashboard and QuickBooks monthly rows share periods."
        ),
        "hasData": bool(rows),
    }


def _collections_vs_qb(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compare latest SoftDent collections to QuickBooks revenue (Phase 5 briefing)."""
    bundle = bundle or load_import_bundle(sync=False)
    sd_rows = _dashboard_rows(bundle)
    qb_rows = _qb_monthly_rows(bundle)
    if not sd_rows or not qb_rows:
        return {"hasData": False, "variancePct": None, "summary": ""}
    latest_sd = sd_rows[-1]
    period = latest_sd["period"]
    collections = float(latest_sd.get("collections") or 0)
    qb_match = next((row for row in qb_rows if row["period"] == period), qb_rows[-1])
    qb_revenue = float(qb_match.get("revenue") or 0)
    if collections <= 0 or qb_revenue <= 0:
        return {"hasData": False, "variancePct": None, "summary": ""}
    variance_pct = round(((qb_revenue - collections) / collections) * 100, 1)
    tone = "ok" if abs(variance_pct) <= 5 else ("warn" if abs(variance_pct) <= 12 else "alert")
    return {
        "hasData": True,
        "period": period,
        "softdentCollections": round(collections, 2),
        "quickbooksRevenue": round(qb_revenue, 2),
        "variancePct": variance_pct,
        "tone": tone,
        "summary": (
            f"{period}: QuickBooks revenue is {variance_pct:+.1f}% vs SoftDent collections "
            f"(${collections:,.0f} collected vs ${qb_revenue:,.0f} QB revenue)."
        ),
    }


def _qb_deposits_for_period(bundle: dict[str, Any], period: str) -> tuple[float | None, str]:
    qb = bundle.get("quickbooks") if isinstance(bundle, dict) else {}
    if not isinstance(qb, dict):
        qb = {}
    summary = qb.get("depositsSummary") or qb.get("deposits_summary")
    if isinstance(summary, dict):
        dep = _parse_money(summary.get("totalDeposits") or summary.get("total_deposits"))
        if dep > 0:
            return dep, "quickbooks.depositsSummary"
    dep_rows = (qb.get("deposits") or {}).get("rows") if isinstance(qb.get("deposits"), dict) else qb.get("deposits")
    if isinstance(dep_rows, list):
        for row in reversed(dep_rows):
            if not isinstance(row, dict):
                continue
            row_period = _normalize_period(row.get("Period") or row.get("period"))
            if row_period and row_period != period:
                continue
            dep = _parse_money(row.get("Deposits") or row.get("deposits") or row.get("amount"))
            if dep > 0:
                return dep, "quickbooks.deposits"
    try:
        from nr2_qb_reports import load_probe_summary

        probe = load_probe_summary()
    except Exception:
        probe = {}
    if isinstance(probe, dict) and probe:
        for key in ("total_deposits", "deposits_total", "bank_deposits"):
            dep = _parse_money(probe.get(key))
            if dep > 0:
                return dep, "quickbooks_sdk_probe"
        by_period = probe.get("deposits_by_period") or probe.get("monthly_deposits")
        if isinstance(by_period, list):
            match = next(
                (
                    item
                    for item in by_period
                    if isinstance(item, dict) and _normalize_period(item.get("period") or item.get("Period")) == period
                ),
                None,
            )
            if match:
                dep = _parse_money(match.get("amount") or match.get("total") or match.get("Deposits"))
                if dep > 0:
                    return dep, "quickbooks_sdk_probe.period"
            if by_period:
                last = by_period[-1]
                if isinstance(last, dict):
                    dep = _parse_money(last.get("amount") or last.get("total") or last.get("Deposits"))
                    if dep > 0:
                        return dep, "quickbooks_sdk_probe.latest"
        payments = _parse_money(probe.get("payments_received") or probe.get("total_payments_received"))
        if payments > 0:
            return payments, "quickbooks_sdk_probe.payments_received"
    return None, ""


def collection_deposit_variance(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compare SoftDent collections to QuickBooks bank deposits for the same period."""
    bundle = bundle or load_import_bundle(sync=False)
    sd_rows = _dashboard_rows(bundle)
    if not sd_rows:
        return {
            "hasData": False,
            "variancePct": None,
            "summary": "Collection vs deposit variance populates when SoftDent dashboard and QuickBooks deposit exports share a period.",
        }
    latest_sd = sd_rows[-1]
    period = latest_sd["period"]
    collections = float(latest_sd.get("collections") or 0)
    deposits, source = _qb_deposits_for_period(bundle, period)
    if collections <= 0 or deposits is None or deposits <= 0:
        return {
            "hasData": False,
            "period": period,
            "softdentCollections": round(collections, 2) if collections else None,
            "quickbooksDeposits": round(deposits, 2) if deposits else None,
            "variancePct": None,
            "summary": "",
        }
    variance_pct = round(((deposits - collections) / collections) * 100, 1)
    threshold = float(os.environ.get("NR2_DEPOSIT_VARIANCE_THRESHOLD_PCT", "8"))
    tone = "ok" if abs(variance_pct) <= threshold else ("warn" if abs(variance_pct) <= threshold * 1.5 else "alert")
    return {
        "hasData": True,
        "period": period,
        "softdentCollections": round(collections, 2),
        "quickbooksDeposits": round(deposits, 2),
        "variancePct": variance_pct,
        "thresholdPct": threshold,
        "tone": tone,
        "source": source,
        "summary": (
            f"{period}: QuickBooks deposits are {variance_pct:+.1f}% vs SoftDent collections "
            f"(${collections:,.0f} collected vs ${deposits:,.0f} deposited)."
        ),
    }


def collection_lag(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    bundle = bundle or load_import_bundle(sync=False)
    ar_rows = (((bundle.get("softdent") or {}).get("ar") or {}).get("rows")) or []
    if not isinstance(ar_rows, list):
        ar_rows = []
    dso = _ar_weighted_dso(ar_rows)
    if dso is not None:
        return {
            "avgLagDays": dso,
            "dsoProxy": True,
            "priorPeriodProxy": False,
            "period": None,
            "incompleteCurrent": False,
            "caption": "",
            "source": "softdent.ar aging buckets",
            "summary": f"Weighted collection lag (DSO proxy): {dso} days.",
            "hasData": True,
        }
    sd_rows = _dashboard_rows(bundle)
    latest = sd_rows[-1] if sd_rows else None
    incomplete_current = bool(latest and _period_incomplete(latest))
    complete = None
    for row in reversed(sd_rows):
        if (
            not _period_incomplete(row)
            and (row.get("production") or 0) > 0
            and (row.get("collections") or 0) > 0
        ):
            complete = row
            break
    avg_days = None
    period = None
    if complete:
        prod = float(complete.get("production") or 0)
        coll = float(complete.get("collections") or 0)
        avg_days = round(max(0.0, min(90.0, 30.0 * (1.0 - min(1.0, coll / prod)))), 1)
        period = complete.get("period")
    prior_period_proxy = bool(
        incomplete_current and period and latest and period != latest.get("period")
    )
    caption = ""
    summary = "Collection lag appears when SoftDent A/R aging or dashboard collections export is loaded."
    if avg_days is not None:
        if prior_period_proxy:
            caption = f"Proxy from {period} · {latest.get('period')} export pending"
            summary = (
                f"Collection lag proxy from {period}: {avg_days} days "
                f"(current month collections export pending)."
            )
        else:
            caption = f"From {period}" if period else ""
            summary = f"Collection lag (monthly proxy): {avg_days} days"
    return {
        "avgLagDays": avg_days,
        "dsoProxy": False,
        "priorPeriodProxy": prior_period_proxy,
        "period": period,
        "incompleteCurrent": incomplete_current,
        "caption": caption,
        "source": "monthly production/collections proxy",
        "summary": summary,
        "hasData": avg_days is not None,
    }


def quickbooks_monthly_revenue(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    bundle = bundle or load_import_bundle(sync=False)
    rows = _qb_monthly_rows(bundle)[-12:]
    return {
        "labels": [row["period"] for row in rows],
        "values": [row["revenue"] for row in rows],
        "hasData": bool(rows),
    }


def softdent_production_daily(*, bundle: dict[str, Any] | None = None, limit: int = 30) -> dict[str, Any]:
    bundle = bundle or load_import_bundle(sync=False)
    sd_daily = _sd_procedures_daily(limit=limit)
    if sd_daily:
        return {"granularity": "daily", "points": sd_daily, "hasData": True, "source": "sd_procedures"}
    daily = _daysheet_daily_production(limit=limit)
    if daily:
        return {"granularity": "daily", "points": daily, "hasData": True, "source": "daysheet"}
    sd_rows = _dashboard_rows(bundle)[-limit:]
    if sd_rows:
        return {
            "granularity": "monthly",
            "points": [{"date": row["period"], "production": row["production"]} for row in sd_rows],
            "hasData": True,
        }
    dashboard_path = softdent_import_dir() / "softdent_dashboard_data.json"
    if dashboard_path.is_file():
        try:
            payload = json.loads(dashboard_path.read_text(encoding="utf-8-sig"))
            if isinstance(payload, list) and payload:
                rows = _dashboard_rows({"softdent": {"dashboard": payload}})
                if rows:
                    return {
                        "granularity": "monthly",
                        "points": [{"date": row["period"], "production": row["production"]} for row in rows[-limit:]],
                        "hasData": True,
                    }
        except json.JSONDecodeError:
            pass
    return {"granularity": "none", "points": [], "hasData": False}


def kpi_ribbon(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    bundle = bundle or load_import_bundle(sync=False)
    recon = production_reconciliation(bundle=bundle)
    lag = collection_lag(bundle=bundle)
    revenue = quickbooks_monthly_revenue(bundle=bundle)
    daily = softdent_production_daily(bundle=bundle, limit=1)
    tiles: list[dict[str, Any]] = []
    latest = recon.get("latest") or {}
    if latest.get("variancePct") is not None:
        tiles.append(
            {
                "label": "Prod vs QB variance",
                "value": f"{latest['variancePct']}%",
                "tone": latest.get("tone") or "neutral",
                "widgetKey": "nr2ProductionReconciliation",
            }
        )
    if lag.get("avgLagDays") is not None:
        tiles.append(
            {
                "label": "Collection lag (DSO)",
                "value": f"{lag['avgLagDays']}d",
                "tone": "warn" if lag["avgLagDays"] > 45 else "ok",
                "widgetKey": "nr2CollectionLag",
            }
        )
    rev_vals = revenue.get("values") or []
    if rev_vals:
        tiles.append(
            {
                "label": "QB revenue (latest month)",
                "value": f"${rev_vals[-1]:,.0f}",
                "tone": "neutral",
                "widgetKey": "quickbooksMonthlyRevenue",
            }
        )
    daily_pts = daily.get("points") or []
    if daily_pts:
        tiles.append(
            {
                "label": "SoftDent production (latest)",
                "value": f"${daily_pts[-1]['production']:,.0f}",
                "tone": "neutral",
                "widgetKey": "softdentProductionDaily",
            }
        )
    coll_vs_qb = _collections_vs_qb(bundle=bundle)
    if coll_vs_qb.get("hasData") and coll_vs_qb.get("variancePct") is not None:
        tiles.append(
            {
                "label": "Collections vs QB",
                "value": f"{coll_vs_qb['variancePct']:+.1f}%",
                "tone": coll_vs_qb.get("tone") or "neutral",
                "widgetKey": "nr2CollectionLag",
            }
        )
    dep_var = collection_deposit_variance(bundle=bundle)
    if dep_var.get("hasData") and dep_var.get("variancePct") is not None:
        tiles.append(
            {
                "label": "Collections vs deposits",
                "value": f"{dep_var['variancePct']:+.1f}%",
                "tone": dep_var.get("tone") or "neutral",
                "widgetKey": "nr2ProductionReconciliation",
            }
        )
    return {"tiles": tiles[:6], "hasData": bool(tiles), "generatedAt": datetime.now(timezone.utc).isoformat()}


def analytics_snapshot(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    bundle = bundle or load_import_bundle(sync=False)
    return {
        "productionReconciliation": production_reconciliation(bundle=bundle),
        "collectionLag": collection_lag(bundle=bundle),
        "quickbooksMonthlyRevenue": quickbooks_monthly_revenue(bundle=bundle),
        "softdentProductionDaily": softdent_production_daily(bundle=bundle),
        "kpiRibbon": kpi_ribbon(bundle=bundle),
        "collectionsVsQuickbooks": _collections_vs_qb(bundle=bundle),
        "collectionDepositVariance": collection_deposit_variance(bundle=bundle),
        "goalScorecard": goal_scorecard(bundle=bundle),
        "alertTicker": alert_ticker(bundle=bundle),
        "providerCompensation": provider_compensation(bundle=bundle),
        "monthlyTrendCombo": monthly_trend_combo(bundle=bundle),
    }


def goal_scorecard(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    import os

    bundle = bundle or load_import_bundle(sync=False)
    sd_rows = _dashboard_rows(bundle)
    ytd_prod = sum(row["production"] for row in sd_rows)
    env_target = os.environ.get("NR2_GOAL_PRODUCTION_YTD", "").strip()
    target = _parse_money(env_target) if env_target else 0.0
    # Never invent a synthetic target (e.g. 105% of YTD) — require an explicit goal.
    if target <= 0:
        return {
            "ytdProduction": round(ytd_prod, 2),
            "targetProduction": None,
            "pctOfGoal": None,
            "tone": "neutral",
            "hasData": ytd_prod > 0,
            "needsGoal": ytd_prod > 0,
        }
    pct = round((ytd_prod / target) * 100, 1)
    tone = "ok" if pct >= 95 else "warn" if pct >= 80 else "alert"
    return {
        "ytdProduction": round(ytd_prod, 2),
        "targetProduction": round(target, 2),
        "pctOfGoal": pct,
        "tone": tone,
        "hasData": True,
        "needsGoal": False,
    }


def alert_ticker(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    bundle = bundle or load_import_bundle(sync=False)
    alerts: list[dict[str, Any]] = []
    recon = production_reconciliation(bundle=bundle)
    latest = recon.get("latest") or {}
    variance = latest.get("variancePct")
    if variance is not None and abs(float(variance)) > 10:
        alerts.append(
            {
                "level": "warn",
                "text": f"Production vs QuickBooks variance {variance}% ({latest.get('period', 'latest')})",
                "widgetKey": "nr2ProductionReconciliation",
            }
        )
    lag = collection_lag(bundle=bundle)
    avg_lag = lag.get("avgLagDays")
    if avg_lag is not None and float(avg_lag) > 45:
        alerts.append(
            {
                "level": "warn",
                "text": f"Collection lag {avg_lag} days exceeds 45-day review threshold",
                "widgetKey": "nr2CollectionLag",
            }
        )
    dep_var = collection_deposit_variance(bundle=bundle)
    dep_variance = dep_var.get("variancePct")
    dep_threshold = dep_var.get("thresholdPct") or 8.0
    if dep_variance is not None and dep_var.get("hasData") and abs(float(dep_variance)) > float(dep_threshold):
        alerts.append(
            {
                "level": "warn" if abs(float(dep_variance)) <= float(dep_threshold) * 1.5 else "alert",
                "text": f"Collections vs QB deposits variance {dep_variance}% ({dep_var.get('period', 'latest')})",
                "widgetKey": "nr2ProductionReconciliation",
            }
        )
    ar_rows = (((bundle.get("softdent") or {}).get("ar") or {}).get("rows")) or []
    if isinstance(ar_rows, list):
        ninety_plus = 0.0
        total = 0.0
        for row in ar_rows:
            if not isinstance(row, dict):
                continue
            amount = _parse_money(row.get("Balance") or row.get("Outstanding") or row.get("Amount"))
            total += amount
            bucket = str(row.get("Aging") or row.get("Bucket") or "")
            if re.search(r"90\+|91\+|120", bucket):
                ninety_plus += amount
        if total > 0 and (ninety_plus / total) >= 0.15:
            alerts.append(
                {
                    "level": "warn",
                    "text": f"A/R 90+ bucket is {round((ninety_plus / total) * 100, 1)}% of outstanding receivables",
                    "widgetKey": "arAgingAndCollections",
                }
            )
    if not alerts:
        alerts.append(
            {
                "level": "ok",
                "text": "Cross-analytics within normal review thresholds for imported snapshot",
                "widgetKey": "nr2KpiRibbon",
            }
        )
    return {"items": alerts[:8], "hasData": True}


def provider_compensation(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    bundle = bundle or load_import_bundle(sync=False)
    providers: list[dict[str, Any]] = []
    try:
        from nr2_softdent_daily import provider_production

        payload = provider_production()
        providers = payload.get("providers") if isinstance(payload.get("providers"), list) else []
    except ImportError:
        providers = []
    if not providers:
        fin = (bundle.get("financial") if isinstance(bundle.get("financial"), dict) else {}) or {}
        sd = bundle.get("softdent") if isinstance(bundle.get("softdent"), dict) else {}
        provider_block = fin.get("providers") or sd.get("providers") or {}
        raw_rows = provider_block.get("rows") if isinstance(provider_block, dict) else provider_block
        if isinstance(raw_rows, list):
            for row in raw_rows[:8]:
                if not isinstance(row, dict):
                    continue
                providers.append(
                    {
                        "name": str(row.get("name") or row.get("provider") or "Provider"),
                        "production": _parse_money(row.get("production") or row.get("amount")),
                    }
                )
    total = sum(_parse_money(item.get("production")) for item in providers)
    rows = []
    for item in providers[:8]:
        amount = _parse_money(item.get("production"))
        rows.append(
            {
                "name": str(item.get("name") or "Provider"),
                "production": round(amount, 2),
                "pct": round((amount / total) * 100, 1) if total > 0 else 0,
            }
        )
    return {"providers": rows, "totalProduction": round(total, 2), "hasData": bool(rows)}


def monthly_trend_combo(*, bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    bundle = bundle or load_import_bundle(sync=False)
    sd_rows = _dashboard_rows(bundle)
    qb_by = {row["period"]: row["revenue"] for row in _qb_monthly_rows(bundle)}
    periods = sorted({row["period"] for row in sd_rows} | set(qb_by.keys()))[-12:]
    labels: list[str] = []
    production: list[float] = []
    collections: list[float] = []
    revenue: list[float] = []
    for period in periods:
        sd = next((row for row in sd_rows if row["period"] == period), None)
        labels.append(period)
        production.append(round(sd["production"], 2) if sd else 0.0)
        collections.append(round(sd["collections"], 2) if sd else 0.0)
        revenue.append(round(qb_by.get(period, 0.0), 2))
    return {
        "labels": labels,
        "production": production,
        "collections": collections,
        "revenue": revenue,
        "hasData": bool(labels),
    }
