"""Compare SoftDent desktop Register Excel vs analytics daysheet_totals (widget drift).

Period money widgets read analytics dashboard rows that are fed by desktop Excel.
This check flags when Register XLS and daysheet_totals disagree so Vital Signs /
Ins-Patient do not silently drift from SoftDent's own Register.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from softdent_odbc_extract import resolve_sd_sqlite_db
from softdent_practice_exports import parse_softdent_register_xls

EXPORT_ROOT = Path(r"C:\SoftDentReportExports")
DEFAULT_TOLERANCE = 0.05  # dollars


def _find_register_xls(*, start: date, end: date) -> Path | None:
    exact = EXPORT_ROOT / f"register_for_period_{start.isoformat()}_{end.isoformat()}.xls"
    if exact.is_file():
        return exact
    # Prefer any July-style match for the month
    cands = sorted(
        EXPORT_ROOT.glob(f"register_for_period_{start.year:04d}-{start.month:02d}*.xls"),
        key=lambda p: p.stat().st_mtime,
    )
    if cands:
        return cands[-1]
    cands = sorted(EXPORT_ROOT.glob("register_for_period_*.xls"), key=lambda p: p.stat().st_mtime)
    return cands[-1] if cands else None


def _daysheet_totals_row(period: str) -> dict[str, Any] | None:
    db = resolve_sd_sqlite_db()
    if not db or not db.is_file():
        return None
    con = sqlite3.connect(str(db))
    try:
        cur = con.cursor()
        cur.execute("PRAGMA table_info(daysheet_totals)")
        cols = [r[1] for r in cur.fetchall()]
        if not cols:
            return None
        if "year_month" in cols:
            cur.execute("SELECT * FROM daysheet_totals WHERE year_month = ? LIMIT 1", (period,))
        else:
            return None
        row = cur.fetchone()
        if not row:
            return None
        return dict(zip(cols, row))
    finally:
        con.close()


def compare_register_to_daysheet_totals(
    *,
    start: date | None = None,
    end: date | None = None,
    tolerance: float = DEFAULT_TOLERANCE,
) -> dict[str, Any]:
    """Return drift report: Register Excel (source of truth) vs daysheet_totals."""
    today = date.today()
    start = start or date(today.year, today.month, 1)
    end = end or today
    period = f"{start.year:04d}-{start.month:02d}"

    result: dict[str, Any] = {
        "ok": False,
        "period": period,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "tolerance": tolerance,
        "registerPath": None,
        "register": None,
        "daysheetTotals": None,
        "deltas": {},
        "driftFields": [],
        "nextStep": None,
    }

    path = _find_register_xls(start=start, end=end)
    if not path:
        result["error"] = "register_xls_missing"
        result["nextStep"] = (
            "SoftDent Sign On → Reports → Accounting → Registers → Period → "
            "click Excel → Enter → save under C:\\SoftDentReportExports."
        )
        return result
    result["registerPath"] = str(path)
    parsed = parse_softdent_register_xls(path)
    if not parsed:
        result["error"] = "register_parse_failed"
        return result
    result["register"] = {
        "production": parsed.get("production"),
        "collections": parsed.get("collections"),
        "insPlanCollections": parsed.get("insPlanCollections"),
        "regularCollections": parsed.get("regularCollections"),
        "collectionsFormatRequired": parsed.get("collectionsFormatRequired"),
    }

    db_row = _daysheet_totals_row(period)
    if not db_row:
        result["error"] = "daysheet_totals_row_missing"
        result["nextStep"] = (
            "Run refresh_softdent_period_imports after Register/Daysheet Excel lands "
            "so analytics daysheet_totals gets a period row."
        )
        result["ok"] = True  # Register present; DB lag is the finding
        result["driftFields"] = ["daysheet_totals_missing"]
        return result

    # Map SoftDent Register labels → daysheet_totals columns
    pairs = [
        ("production", "gross_production", parsed.get("production")),
        ("collections", "collections", parsed.get("collections")),
    ]
    # Prefer gross_production; also note net_production separately
    result["daysheetTotals"] = {
        "gross_production": db_row.get("gross_production"),
        "net_production": db_row.get("net_production"),
        "collections": db_row.get("collections"),
        "year_month": db_row.get("year_month"),
        "report_period_start": db_row.get("report_period_start"),
        "report_period_end": db_row.get("report_period_end"),
    }

    drift: list[str] = []
    deltas: dict[str, Any] = {}
    for label, col, reg_val in pairs:
        db_val = db_row.get(col)
        try:
            r = float(reg_val) if reg_val is not None else None
            d = float(db_val) if db_val is not None else None
        except (TypeError, ValueError):
            r, d = None, None
        if r is None or d is None:
            deltas[label] = {"register": reg_val, "daysheet_totals": db_val, "delta": None}
            drift.append(label)
            continue
        delta = round(d - r, 2)
        deltas[label] = {
            "register": r,
            "daysheet_totals": d,
            "delta": delta,
            "withinTolerance": abs(delta) <= tolerance,
        }
        if abs(delta) > tolerance:
            drift.append(label)

    result["deltas"] = deltas
    result["driftFields"] = drift
    result["ok"] = len(drift) == 0
    if drift:
        result["nextStep"] = (
            "Desktop Register Excel is source of truth for period $. "
            "Re-export Register/Daysheet Excel and refresh period imports, or investigate "
            f"why daysheet_totals differs on: {', '.join(drift)}."
        )
    else:
        result["nextStep"] = "Register Excel and daysheet_totals agree within tolerance."
    return result


def format_drift_hal_reply(report: dict[str, Any] | None = None) -> str:
    r = report if isinstance(report, dict) else compare_register_to_daysheet_totals()
    period = r.get("period") or "period"
    if r.get("error") == "register_xls_missing":
        return (
            f"No SoftDent Register Excel for {period} in SoftDentReportExports. "
            "Money widgets need desktop Register → Excel → Enter → refresh."
        )
    if r.get("driftFields") == ["daysheet_totals_missing"]:
        return (
            f"Register Excel is present for {period}, but analytics daysheet_totals "
            "has no row yet — run SoftDent period refresh so Vital Signs can load."
        )
    if r.get("ok"):
        reg = r.get("register") or {}
        return (
            f"Register Excel and daysheet_totals agree for {period} "
            f"(production {reg.get('production')}, collections {reg.get('collections')}). "
            "Period money widgets can trust the dashboard row."
        )
    parts = [f"SoftDent period $ drift for {period} (Register Excel is source of truth):"]
    for field, meta in (r.get("deltas") or {}).items():
        if not isinstance(meta, dict):
            continue
        if meta.get("withinTolerance"):
            continue
        parts.append(
            f"{field}: Register {meta.get('register')} vs daysheet_totals "
            f"{meta.get('daysheet_totals')} (delta {meta.get('delta')})."
        )
    parts.append(str(r.get("nextStep") or "Re-export Register Excel and refresh."))
    return " ".join(parts)


def main() -> int:
    import argparse
    from datetime import date as date_cls

    today = date_cls.today()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=f"{today.year:04d}-{today.month:02d}-01")
    parser.add_argument("--end", default=today.isoformat())
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    args = parser.parse_args()
    report = compare_register_to_daysheet_totals(
        start=date_cls.fromisoformat(args.start),
        end=date_cls.fromisoformat(args.end),
        tolerance=float(args.tolerance),
    )
    print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
