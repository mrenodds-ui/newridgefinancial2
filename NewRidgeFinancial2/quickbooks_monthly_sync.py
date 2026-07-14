"""Build monthly QuickBooks P&L import rows for NR2 dashboards.

Sources (in priority order):
1. ``monthly`` array on the SDK probe summary JSON
2. ``quickbooks_profit_loss_summary`` in the SoftDent financial analytics DB
3. Optional per-month QuickBooks Desktop SDK reads (auto when fewer than two months exist)
"""

from __future__ import annotations

import calendar
import csv
import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
LEGACY_ROOT = REPO_ROOT / "_legacy"
SOFTDENT_FINANCIAL_EXPORTS = Path(r"C:\SoftDentFinancialExports")
ANALYTICS_DB = SOFTDENT_FINANCIAL_EXPORTS / "softdent_financial_analytics.db"
QB_SDK_SUMMARY = SOFTDENT_FINANCIAL_EXPORTS / "quickbooks_diagnostics" / "quickbooks_sdk_report_probe_summary.json"


def _env_path(name: str, default: Path | None = None) -> Path | None:
    configured = os.environ.get(name, "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        return candidate.resolve()
    return default.resolve() if default else None


def resolve_analytics_db() -> Path | None:
    candidate = _env_path("NR2_FINANCIAL_ANALYTICS_DB")
    if candidate and candidate.is_file():
        return candidate
    if os.environ.get("NR2_AUTO_PULL_EXPORTS", "1").strip().lower() not in {"0", "false", "no", "off"}:
        return ANALYTICS_DB if ANALYTICS_DB.is_file() else None
    return None


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> bool:
    from import_cache_ttl import write_bytes_if_changed

    path.parent.mkdir(parents=True, exist_ok=True)
    buf = __import__("io").StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in fieldnames})
    return write_bytes_if_changed(path, buf.getvalue().encode("utf-8"))


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _month_start_end(year_month: str) -> tuple[str, str] | None:
    try:
        year_str, month_str = year_month.split("-", 1)
        year = int(year_str)
        month = int(month_str)
        last_day = calendar.monthrange(year, month)[1]
        return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"
    except (TypeError, ValueError):
        return None


def _round_money(value: Any) -> float | None:
    coerced = _coerce_float(value)
    if coerced is None:
        return None
    return round(coerced, 2)


def _normalize_monthly_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_period: dict[str, dict[str, Any]] = {}
    for row in rows:
        period = str(row.get("Period") or row.get("period") or row.get("year_month") or "").strip()
        revenue = _round_money(row.get("TotalIncome") or row.get("income_total") or row.get("revenue"))
        expenses = _round_money(row.get("TotalExpense") or row.get("expense_total") or row.get("expenses"))
        if not period or revenue is None or expenses is None:
            continue
        net_income = _round_money(row.get("NetIncome") or row.get("net_income"))
        if net_income is None:
            net_income = _round_money(revenue - expenses)
        candidate = {
            "Period": period,
            "TotalIncome": revenue,
            "TotalExpense": expenses,
            "NetIncome": net_income,
            "period_start": str(row.get("period_start") or ""),
            "period_end": str(row.get("period_end") or ""),
            "source": str(row.get("source") or "unknown"),
            "imported_at_utc": str(row.get("imported_at_utc") or ""),
        }
        existing = by_period.get(period)
        if existing is None or _month_row_score(candidate) > _month_row_score(existing):
            by_period[period] = candidate
    monthly = list(by_period.values())
    monthly.sort(key=lambda item: item["Period"])
    return monthly


def _month_row_score(row: dict[str, Any]) -> tuple[int, str]:
    period = row["Period"]
    start = str(row.get("period_start") or "")
    end = str(row.get("period_end") or "")
    month_bounds = _month_start_end(period)
    score = 0
    if month_bounds and start == month_bounds[0]:
        score += 3
    if month_bounds and end == month_bounds[1]:
        score += 2
    elif month_bounds and end.startswith(period):
        score += 1
    if start and end and start[:7] == period and end[:7] == period:
        score += 1
    return (score, str(row.get("imported_at_utc") or ""))


def _rows_from_probe_monthly(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    monthly = payload.get("monthly")
    if not isinstance(monthly, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in monthly:
        if not isinstance(item, dict):
            continue
        period = str(item.get("period") or item.get("year_month") or item.get("Period") or "").strip()
        revenue = _coerce_float(item.get("total_income") or item.get("TotalIncome"))
        expenses = _coerce_float(item.get("total_expenses") or item.get("TotalExpense"))
        if not period or revenue is None or expenses is None:
            continue
        rows.append(
            {
                "Period": period,
                "TotalIncome": revenue,
                "TotalExpense": expenses,
                "NetIncome": _coerce_float(item.get("net_income") or item.get("NetIncome")) or (revenue - expenses),
                "period_start": item.get("period_start") or "",
                "period_end": item.get("period_end") or "",
                "source": "probe-monthly",
                "imported_at_utc": str(payload.get("generated_at_utc") or ""),
            }
        )
    return _normalize_monthly_rows(rows)


def _rows_from_analytics_db(db_path: Path) -> list[dict[str, Any]]:
    import sqlite3

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='quickbooks_profit_loss_summary'"
        ).fetchone()
        if not table:
            return []
        raw_rows = connection.execute(
            """
            SELECT year_month, period_start, period_end, income_total, expense_total, net_income, imported_at_utc
            FROM quickbooks_profit_loss_summary
            ORDER BY imported_at_utc ASC
            """
        ).fetchall()
    rows = [
        {
            "Period": str(row["year_month"] or ""),
            "TotalIncome": row["income_total"],
            "TotalExpense": row["expense_total"],
            "NetIncome": row["net_income"],
            "period_start": row["period_start"],
            "period_end": row["period_end"],
            "source": "analytics-db",
            "imported_at_utc": row["imported_at_utc"],
        }
        for row in raw_rows
    ]
    from import_cache_ttl import relevant_period_labels

    allowed = set(relevant_period_labels())
    rows = [row for row in rows if str(row.get("Period") or "") in allowed]
    return _normalize_monthly_rows(rows)


def _iter_relevant_months(max_months: int = 2) -> list[tuple[str, str, str]]:
    """Current month (MTD) and prior full month — not multi-year history."""
    today = date.today()
    year = today.year
    month = today.month
    periods: list[tuple[str, str, str]] = []
    limit = max(1, min(max_months, 3))
    for _ in range(limit):
        label = f"{year:04d}-{month:02d}"
        bounds = _month_start_end(label)
        if bounds:
            start, end = bounds
            if label == f"{today.year:04d}-{today.month:02d}":
                end = today.isoformat()
            periods.append((label, start, end))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    periods.reverse()
    return periods


def _fetch_sdk_topic(topic: str, start: str, end: str) -> float | None:
    python = sys.executable
    command = [python, "-m", "app.quickbooks_sdk_runner", topic, start, end]
    try:
        completed = subprocess.run(
            command,
            cwd=str(LEGACY_ROOT if LEGACY_ROOT.is_dir() else REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=max(int(os.environ.get("NR2_QB_MONTHLY_SDK_TIMEOUT", "90")), 30),
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, list) or not payload:
        return None
    row = payload[0]
    if not isinstance(row, dict):
        return None
    if topic == "revenue":
        return _coerce_float(row.get("TotalIncome") or row.get("Amount"))
    return _coerce_float(row.get("TotalExpense") or row.get("Amount"))


def _rows_from_sdk_monthly(month_count: int) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    for period, start, end in _iter_relevant_months(month_count):
        revenue = _fetch_sdk_topic("revenue", start, end)
        expenses = _fetch_sdk_topic("expenses", start, end)
        if revenue is None or expenses is None:
            warnings.append(f"QuickBooks SDK monthly read unavailable for {period}.")
            continue
        rows.append(
            {
                "Period": period,
                "TotalIncome": revenue,
                "TotalExpense": expenses,
                "NetIncome": revenue - expenses,
                "period_start": start,
                "period_end": end,
                "source": "sdk-monthly",
                "imported_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
    return _normalize_monthly_rows(rows), warnings


def _should_fetch_sdk_monthly(existing_months: int, *, force: bool = False) -> bool:
    if force:
        mode = os.environ.get("NR2_QB_MONTHLY_SDK", "auto").strip().lower()
        if mode in {"0", "false", "no", "off"}:
            return False
        return True
    if os.environ.get("NR2_AUTO_PULL_EXPORTS", "1").strip().lower() in {"0", "false", "no", "off"}:
        return False
    mode = os.environ.get("NR2_QB_MONTHLY_SDK", "auto").strip().lower()
    if mode in {"0", "false", "no", "off"}:
        return False
    if mode in {"1", "true", "yes", "on"}:
        return True
    if existing_months >= 2:
        return False
    for candidate in (
        _env_path("NR2_QB_PROBE_PATH"),
        REPO_ROOT / "app_data" / "nr2" / "document_inbox" / "quickbooks" / "quickbooks_sdk_report_probe_summary.json",
        QB_SDK_SUMMARY,
    ):
        if not candidate or not candidate.is_file():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            status = str(payload.get("status") or "").upper()
            if status and status != "QUICKBOOKS_SDK_REPORT_DATA_AVAILABLE":
                return False
            break
    return existing_months < 2


def _write_monthly_exports(destination: Path, monthly_rows: list[dict[str, Any]]) -> list[str]:
    if not monthly_rows:
        return []
    written: list[str] = []
    revenue_rows = [{"Period": row["Period"], "TotalIncome": row["TotalIncome"]} for row in monthly_rows]
    expense_rows = [{"Period": row["Period"], "TotalExpense": row["TotalExpense"]} for row in monthly_rows]
    pl_rows = [
        {
            "Period": row["Period"],
            "TotalIncome": row["TotalIncome"],
            "TotalExpense": row["TotalExpense"],
            "NetIncome": row["NetIncome"],
        }
        for row in monthly_rows
    ]
    revenue_path = destination / "quickbooks_revenue.csv"
    expense_path = destination / "quickbooks_expenses.csv"
    pl_path = destination / "quickbooks_profit_and_loss.csv"
    _write_csv(revenue_path, revenue_rows, ["Period", "TotalIncome"])
    _write_csv(expense_path, expense_rows, ["Period", "TotalExpense"])
    _write_csv(pl_path, pl_rows, ["Period", "TotalIncome", "TotalExpense", "NetIncome"])
    written.extend([revenue_path.name, expense_path.name, pl_path.name])
    return written


def _newest_quickbooks_export_mtime(destination: Path) -> float | None:
    best: float | None = None
    for name in (
        "quickbooks_profit_and_loss.csv",
        "quickbooks_revenue.csv",
        "quickbooks_expenses.csv",
        "quickbooks_expense_categories.csv",
    ):
        path = destination / name
        if not path.is_file():
            continue
        mtime = path.stat().st_mtime
        if best is None or mtime > best:
            best = mtime
    return best


def quickbooks_cache_stale(destination: Path, max_age_minutes: int = 60) -> bool:
    destination = Path(destination)
    if not destination.is_dir():
        return True
    mtime = _newest_quickbooks_export_mtime(destination)
    if mtime is None:
        return True
    return (datetime.now(timezone.utc).timestamp() - mtime) > max(1, max_age_minutes) * 60


def ensure_quickbooks_fresh(
    destination: Path | None = None,
    *,
    max_age_minutes: int = 60,
    probe_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from import_loader import quickbooks_import_dir

    destination = Path(destination or quickbooks_import_dir())
    stale = quickbooks_cache_stale(destination, max_age_minutes)
    result: dict[str, Any] = {
        "stale": stale,
        "refreshed": False,
        "destination": str(destination),
        "sync": None,
    }
    if not stale:
        return result
    sync = sync_quickbooks_monthly_exports(
        destination,
        probe_payload=probe_payload,
        force_sdk=True,
    )
    result["refreshed"] = bool(sync.get("written"))
    result["sync"] = sync
    return result


def sync_quickbooks_monthly_exports(
    destination: Path,
    *,
    probe_payload: dict[str, Any] | None = None,
    force_sdk: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "months": 0,
        "written": [],
        "sources": [],
        "warnings": [],
    }
    monthly_rows: list[dict[str, Any]] = []

    probe_rows = _rows_from_probe_monthly(probe_payload)
    if probe_rows:
        monthly_rows = probe_rows
        result["sources"].append("probe-monthly")

    if len(monthly_rows) < 2:
        db_path = resolve_analytics_db()
        if db_path:
            analytics_rows = _rows_from_analytics_db(db_path)
            if analytics_rows:
                monthly_rows = analytics_rows
                result["sources"].append("analytics-db")

    if _should_fetch_sdk_monthly(len(monthly_rows), force=force_sdk):
        month_count = max(2, min(int(os.environ.get("NR2_QB_MONTHLY_SDK_MONTHS", "2")), 3))
        sdk_rows, sdk_warnings = _rows_from_sdk_monthly(month_count)
        result["warnings"].extend(sdk_warnings)
        if sdk_rows:
            monthly_rows = sdk_rows
            result["sources"].append("sdk-monthly")

    monthly_rows = _normalize_monthly_rows(monthly_rows)
    result["months"] = len(monthly_rows)
    if monthly_rows:
        result["written"] = _write_monthly_exports(destination, monthly_rows)
        result["periods"] = [row["Period"] for row in monthly_rows]
    else:
        result["warnings"].append("No QuickBooks period rows were available for the current or prior month.")
    try:
        from nr2_qb_reports import sync_extended_qb_reports

        extended = sync_extended_qb_reports()
        result["extendedReports"] = {
            "ok": bool(extended.get("ok")),
            "populated": extended.get("populated"),
            "written": extended.get("written"),
        }
    except Exception as exc:
        result["warnings"].append(f"Extended QB reports cache skipped: {exc}")
    return result
