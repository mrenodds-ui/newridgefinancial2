"""Generate optional SoftDent practice widget exports from the analytics DB."""

from __future__ import annotations

import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from import_cache_ttl import relevant_period_labels
from import_loader import softdent_import_dir
from quickbooks_monthly_sync import resolve_analytics_db


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return {str(row[1]) for row in cur.fetchall()}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _aggregate_new_patients(conn: sqlite3.Connection, periods: list[str]) -> list[dict[str, Any]]:
    for table in ("new_patient_counts", "new_patients", "patient_new_counts"):
        if not _table_exists(conn, table):
            continue
        columns = _table_columns(conn, table)
        period_col = next((name for name in ("year_month", "period", "month") if name in columns), None)
        count_col = next((name for name in ("new_patient_count", "count", "new_patients", "total") if name in columns), None)
        if not period_col or not count_col:
            continue
        placeholders = ",".join("?" for _ in periods)
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT {period_col}, SUM(COALESCE({count_col}, 0))
            FROM {table}
            WHERE {period_col} IN ({placeholders})
            GROUP BY {period_col}
            """,
            periods,
        )
        rows = [{"Period": str(period), "Count": int(float(count or 0))} for period, count in cur.fetchall()]
        if rows:
            return rows
    return []


def _aggregate_treatment_plans(conn: sqlite3.Connection, periods: list[str]) -> list[dict[str, Any]]:
    for table in ("treatment_plan_summary", "treatment_plans", "tx_plan_summary"):
        if not _table_exists(conn, table):
            continue
        columns = _table_columns(conn, table)
        period_col = next(
            (name for name in ("year_month", "period", "month", "report_date") if name in columns),
            None,
        )
        presented_col = next(
            (
                name
                for name in (
                    "presented",
                    "plans_presented",
                    "tx_presented",
                    "presented_count",
                    "presented_value",
                )
                if name in columns
            ),
            None,
        )
        accepted_col = next(
            (
                name
                for name in ("accepted", "plans_accepted", "tx_accepted", "accepted_count", "accepted_value")
                if name in columns
            ),
            None,
        )
        amount_col = next((name for name in ("amount", "presented_value", "total_amount") if name in columns), None)
        if not presented_col and not accepted_col:
            continue
        where = ""
        params: list[Any] = []
        group_by = period_col
        period_select = f"{period_col} AS period"
        if period_col and periods:
            placeholders = ",".join("?" for _ in periods)
            if period_col == "report_date":
                period_select = f"substr({period_col}, 1, 7) AS period"
                where = f" WHERE substr({period_col}, 1, 7) IN ({placeholders})"
                group_by = "substr(report_date, 1, 7)"
            else:
                where = f" WHERE {period_col} IN ({placeholders})"
            params = list(periods)
        select_parts = [period_select] if period_col else []
        if presented_col:
            select_parts.append(f"SUM(COALESCE({presented_col}, 0)) AS presented")
        if accepted_col:
            select_parts.append(f"SUM(COALESCE({accepted_col}, 0)) AS accepted")
        if amount_col:
            select_parts.append(f"SUM(COALESCE({amount_col}, 0)) AS amount")
        cur = conn.cursor()
        cur.execute(
            f"SELECT {', '.join(select_parts)} FROM {table}{where}" + (f" GROUP BY {group_by}" if group_by else ""),
            params,
        )
        rows: list[dict[str, Any]] = []
        for raw in cur.fetchall():
            if period_col:
                period, *values = raw
                payload = {"Period": str(period)}
                idx = 0
                if presented_col:
                    payload["Presented"] = float(values[idx] or 0)
                    idx += 1
                if accepted_col:
                    payload["Accepted"] = float(values[idx] or 0)
                    idx += 1
                if amount_col:
                    payload["Amount"] = float(values[idx] or 0)
            else:
                payload = {}
                idx = 0
                if presented_col:
                    payload["Presented"] = float(raw[idx] or 0)
                    idx += 1
                if accepted_col:
                    payload["Accepted"] = float(raw[idx] or 0)
                    idx += 1
                if amount_col:
                    payload["Amount"] = float(raw[idx] or 0)
            rows.append(payload)
        if rows:
            return rows
    return []


def _derive_case_acceptance(tp_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in tp_rows:
        presented = float(row.get("Presented") or 0)
        accepted = float(row.get("Accepted") or 0)
        if presented <= 0:
            continue
        out.append(
            {
                "Period": row.get("Period") or "",
                "Presented": presented,
                "Accepted": accepted,
                "AcceptanceRate": round((accepted / presented) * 100, 1),
            }
        )
    return out


from softdent_dashboard_period_sync import diagnose_collections_gap


def _practice_dataset(
    rows: list[dict[str, Any]],
    *,
    db_path: Path,
    source_file: str,
) -> dict[str, Any]:
    return {
        "sourceFile": source_file,
        "sourcePath": str(db_path),
        "modifiedAt": datetime.fromtimestamp(db_path.stat().st_mtime, tz=timezone.utc).isoformat(),
        "rows": rows,
        "readSource": "direct",
        "sourceKind": "analytics-db",
    }


def read_practice_export_datasets(db_path: Path | None = None) -> dict[str, dict[str, Any] | None]:
    """In-memory practice widget rows from the analytics DB (no document-inbox write)."""
    db_path = db_path or resolve_analytics_db()
    out: dict[str, dict[str, Any] | None] = {
        "newPatients": None,
        "treatmentPlans": None,
        "caseAcceptance": None,
    }
    if not db_path or not db_path.is_file():
        return out

    periods = relevant_period_labels()
    conn = sqlite3.connect(db_path)
    try:
        np_rows = _aggregate_new_patients(conn, periods)
        tp_rows = _aggregate_treatment_plans(conn, periods)
        ca_rows = _derive_case_acceptance(tp_rows) if tp_rows else []
    finally:
        conn.close()

    if np_rows:
        out["newPatients"] = _practice_dataset(np_rows, db_path=db_path, source_file="softdent_new_patients.csv")
    if tp_rows:
        out["treatmentPlans"] = _practice_dataset(tp_rows, db_path=db_path, source_file="treatment_plan_summary.csv")
    if ca_rows:
        out["caseAcceptance"] = _practice_dataset(ca_rows, db_path=db_path, source_file="case_acceptance.csv")
    return out


def sync_practice_exports(db_path: Path | None = None, destination: Path | None = None) -> dict[str, Any]:
    db_path = db_path or resolve_analytics_db()
    destination = destination or softdent_import_dir()
    destination.mkdir(parents=True, exist_ok=True)
    periods = relevant_period_labels()
    written: list[str] = []
    result: dict[str, Any] = {
        "ok": False,
        "written": written,
        "source": str(db_path) if db_path else None,
        "collectionsDiagnostic": diagnose_collections_gap(db_path, periods),
    }
    if not db_path or not db_path.is_file():
        return result

    conn = sqlite3.connect(db_path)
    try:
        np_rows = _aggregate_new_patients(conn, periods)
        if np_rows:
            path = destination / "softdent_new_patients.csv"
            _write_csv(path, np_rows, ["Period", "Count"])
            written.append(path.name)

        tp_rows = _aggregate_treatment_plans(conn, periods)
        if tp_rows:
            fieldnames = [key for key in ("Period", "Presented", "Accepted", "Amount") if any(key in row for row in tp_rows)]
            if not fieldnames:
                fieldnames = list(tp_rows[0].keys())
            path = destination / "treatment_plan_summary.csv"
            _write_csv(path, tp_rows, fieldnames)
            written.append(path.name)

            ca_rows = _derive_case_acceptance(tp_rows)
            if ca_rows:
                ca_path = destination / "case_acceptance.csv"
                _write_csv(ca_path, ca_rows, ["Period", "Presented", "Accepted", "AcceptanceRate"])
                written.append(ca_path.name)
    finally:
        conn.close()

    result["ok"] = bool(written)
    result["written"] = written
    return result


if __name__ == "__main__":
    import json as _json

    print(_json.dumps(sync_practice_exports(), indent=2))
