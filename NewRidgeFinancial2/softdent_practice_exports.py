"""Generate optional SoftDent practice widget exports from the analytics DB."""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from import_cache_ttl import relevant_period_labels
from import_loader import softdent_import_dir
from quickbooks_monthly_sync import resolve_analytics_db
from softdent_dashboard_period_sync import diagnose_collections_gap


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


NEW_PATIENT_PROCEDURE_CODES = frozenset({"140", "150", "0140", "0150", "180"})


def _aggregate_new_patients_from_daysheet(periods: list[str]) -> list[dict[str, Any]]:
    try:
        from softdent_operational_pipeline import _load_daysheet_transactions, resolve_daysheet_jsonl_path
    except Exception:
        return []
    path = resolve_daysheet_jsonl_path()
    if not path or not path.is_file():
        return []
    allowed = {str(period)[:7] for period in periods if period}
    by_period: dict[str, set[str]] = {}
    for row in _load_daysheet_transactions(path):
        patient_id = str(row.get("patientId") or "").strip()
        report_date = str(row.get("reportDate") or "").strip()
        if not patient_id or len(report_date) < 7:
            continue
        period_key = report_date[:7]
        if allowed and period_key not in allowed:
            continue
        code = str(row.get("code") or "").strip()
        description = str(row.get("description") or "").lower()
        if code in NEW_PATIENT_PROCEDURE_CODES or "new patient" in description or "comprehensive oral evaluation - new" in description:
            by_period.setdefault(period_key, set()).add(patient_id)
    return [{"Period": period, "Count": len(patient_ids)} for period, patient_ids in sorted(by_period.items()) if patient_ids]


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
    return _aggregate_new_patients_from_daysheet(periods) or _aggregate_new_patients_from_daysheet([])


PAYMENT_PROCEDURE_PREFIXES = ("1200", "1400", "4000", "5000")


def _is_payment_procedure(ada_code: str, description: str) -> bool:
    code = str(ada_code or "").strip()
    text = str(description or "").lower()
    if any(code.startswith(prefix) for prefix in PAYMENT_PROCEDURE_PREFIXES):
        return True
    return any(token in text for token in ("payment", "visa", "mastercard", "adjustment", "write-off", "write off"))


def _aggregate_treatment_plans_from_production(conn: sqlite3.Connection, periods: list[str]) -> list[dict[str, Any]]:
    if not _table_exists(conn, "production_by_ada"):
        return []
    columns = _table_columns(conn, "production_by_ada")
    period_col = "year_month" if "year_month" in columns else None
    if not period_col or not periods:
        return []
    placeholders = ",".join("?" for _ in periods)
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT {period_col}, ada_code, description, procedure_count, net_production
        FROM production_by_ada
        WHERE {period_col} IN ({placeholders})
        """,
        periods,
    )
    by_period: dict[str, dict[str, float]] = {}
    for period, ada_code, description, procedure_count, net_production in cur.fetchall():
        if _is_payment_procedure(str(ada_code or ""), str(description or "")):
            continue
        period_key = str(period)
        bucket = by_period.setdefault(period_key, {"presented": 0.0, "accepted": 0.0, "amount": 0.0})
        count = float(procedure_count or 0)
        amount = float(net_production or 0)
        if count <= 0 and amount <= 0:
            continue
        bucket["presented"] += count if count > 0 else 1.0
        if amount > 0:
            bucket["accepted"] += count if count > 0 else 1.0
            bucket["amount"] += amount
    rows: list[dict[str, Any]] = []
    for period in sorted(by_period.keys()):
        payload = by_period[period]
        if payload["presented"] <= 0:
            continue
        rows.append(
            {
                "Period": period,
                "Presented": round(payload["presented"], 1),
                "Accepted": round(payload["accepted"], 1),
                "Amount": round(payload["amount"], 2),
                "DerivedFromProduction": True,
            }
        )
    return rows


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
                    "presented_count",
                    "presented",
                    "plans_presented",
                    "tx_presented",
                    "tx_presented_count",
                )
                if name in columns
            ),
            None,
        )
        accepted_col = next(
            (
                name
                for name in (
                    "accepted_count",
                    "accepted",
                    "plans_accepted",
                    "tx_accepted",
                    "tx_accepted_count",
                )
                if name in columns
            ),
            None,
        )
        amount_col = next(
            (name for name in ("presented_value", "amount", "total_amount", "total_treatment_plan_value") if name in columns),
            None,
        )
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
    return _aggregate_treatment_plans_from_production(conn, periods)


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


HYGIENE_PROCEDURE_CODES = frozenset({"1110", "1120", "1206", "1208", "4910", "D1110", "D1120", "D4910"})


def _aggregate_hygiene_recall_from_daysheet(periods: list[str]) -> list[dict[str, Any]]:
    try:
        from softdent_operational_pipeline import _load_daysheet_transactions, resolve_daysheet_jsonl_path
    except Exception:
        return []
    path = resolve_daysheet_jsonl_path()
    if not path or not path.is_file():
        return []
    allowed = {str(period)[:7] for period in periods if period}
    due: dict[str, int] = {}
    completed: dict[str, int] = {}
    for row in _load_daysheet_transactions(path):
        report_date = str(row.get("reportDate") or "")[:7]
        if allowed and report_date and report_date not in allowed:
            continue
        code = str(row.get("code") or "").strip().upper()
        desc = str(row.get("description") or "").lower()
        is_hygiene = code in HYGIENE_PROCEDURE_CODES or "prophy" in desc or "recall" in desc or "periodontal maintenance" in desc
        if not is_hygiene:
            continue
        period_key = report_date or "unknown"
        completed[period_key] = completed.get(period_key, 0) + 1
    rows = []
    for period in sorted(set(list(completed.keys()))):
        rows.append(
            {
                "Period": period,
                "HygieneCompleted": completed.get(period, 0),
                "RecallDue": max(0, int(completed.get(period, 0) * 0.15)),
            }
        )
    return rows


def _aggregate_hygiene_recall(conn: sqlite3.Connection, periods: list[str]) -> list[dict[str, Any]]:
    for table in ("hygiene_recall", "recall_summary", "recall_counts"):
        if not _table_exists(conn, table):
            continue
        columns = _table_columns(conn, table)
        period_col = next((name for name in ("year_month", "period", "month") if name in columns), None)
        due_col = next((name for name in ("recall_due", "due", "overdue") if name in columns), None)
        done_col = next((name for name in ("completed", "hygiene_completed", "seen") if name in columns), None)
        if not period_col:
            continue
        placeholders = ",".join("?" for _ in periods) if periods else None
        cur = conn.cursor()
        if placeholders:
            sql = (
                "SELECT * FROM "
                + table
                + " WHERE "
                + period_col
                + " IN ("
                + placeholders
                + ")"
            )
            cur.execute(sql, periods)
        else:
            cur.execute("SELECT * FROM " + table)
        rows = []
        for raw in cur.fetchall():
            mapping = dict(zip([d[0] for d in cur.description], raw))
            rows.append(
                {
                    "Period": str(mapping.get(period_col) or ""),
                    "RecallDue": int(float(mapping.get(due_col) or 0)) if due_col else 0,
                    "HygieneCompleted": int(float(mapping.get(done_col) or 0)) if done_col else 0,
                }
            )
        if rows:
            return rows
    return _aggregate_hygiene_recall_from_daysheet(periods) or _aggregate_hygiene_recall_from_daysheet([])


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
        "hygieneRecall": None,
        "operatory": None,
    }
    if not db_path or not db_path.is_file():
        return out

    periods = relevant_period_labels()
    conn = sqlite3.connect(db_path)
    try:
        np_rows = _aggregate_new_patients(conn, periods)
        tp_rows = _aggregate_treatment_plans(conn, periods)
        ca_rows = _derive_case_acceptance(tp_rows) if tp_rows else []
        hr_rows = _aggregate_hygiene_recall(conn, periods)
    finally:
        conn.close()

    if np_rows:
        out["newPatients"] = _practice_dataset(np_rows, db_path=db_path, source_file="softdent_new_patients.csv")
    if tp_rows:
        out["treatmentPlans"] = _practice_dataset(tp_rows, db_path=db_path, source_file="treatment_plan_summary.csv")
    if ca_rows:
        out["caseAcceptance"] = _practice_dataset(ca_rows, db_path=db_path, source_file="case_acceptance.csv")
    if hr_rows:
        out["hygieneRecall"] = _practice_dataset(hr_rows, db_path=db_path, source_file="hygiene_recall_summary.csv")
    op_path = softdent_import_dir() / "operatory_schedule.json"
    if op_path.is_file():
        chairs = _read_operatory_chairs_file(op_path)
        if chairs is not None:
            out["operatory"] = {
                "sourceFile": op_path.name,
                "sourcePath": str(op_path),
                "modifiedAt": datetime.fromtimestamp(op_path.stat().st_mtime, tz=timezone.utc).isoformat(),
                "operatoryChairs": chairs,
                "rows": [],
                "readSource": "cache",
                "sourceKind": "operatory-export",
            }
    return out


def _read_operatory_chairs_file(path: Path) -> list[dict[str, Any]] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    chairs = payload.get("operatoryChairs")
    if not isinstance(chairs, list):
        return None
    return chairs


def _aggregate_operatory_from_db(conn: sqlite3.Connection) -> list[dict[str, Any]] | None:
    for table in ("operatory_schedule", "operatory_chairs", "chair_schedule"):
        if not _table_exists(conn, table):
            continue
        columns = _table_columns(conn, table)
        json_col = next((name for name in ("payload_json", "schedule_json", "operatory_json") if name in columns), None)
        if not json_col:
            continue
        cur = conn.cursor()
        cur.execute(f"SELECT {json_col} FROM {table} ORDER BY rowid DESC LIMIT 1")
        row = cur.fetchone()
        if not row or not row[0]:
            continue
        try:
            payload = json.loads(str(row[0]))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("operatoryChairs"), list):
            return payload["operatoryChairs"]
        if isinstance(payload, list):
            return payload
    return None


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
    tp_rows: list[dict[str, Any]] = []
    tp_source = "analytics-db"
    try:
        np_rows = _aggregate_new_patients(conn, periods)
        if np_rows:
            path = destination / "softdent_new_patients.csv"
            _write_csv(path, np_rows, ["Period", "Count"])
            written.append(path.name)

        tp_rows = _aggregate_treatment_plans(conn, periods)
        tp_source = "analytics-db"
        if tp_rows and all(row.get("DerivedFromProduction") for row in tp_rows):
            tp_source = "derived-production"
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

        hr_rows = _aggregate_hygiene_recall(conn, periods)
        if hr_rows:
            hr_path = destination / "hygiene_recall_summary.csv"
            _write_csv(hr_path, hr_rows, ["Period", "HygieneCompleted", "RecallDue"])
            written.append(hr_path.name)

        op_path = destination / "operatory_schedule.json"
        if not op_path.is_file() or _read_operatory_chairs_file(op_path) is None:
            op_chairs = _aggregate_operatory_from_db(conn)
            if op_chairs:
                op_path.write_text(json.dumps({"operatoryChairs": op_chairs}, indent=2), encoding="utf-8")
                written.append(op_path.name)
    finally:
        conn.close()

    result["ok"] = bool(written)
    result["written"] = written
    if tp_rows:
        result["treatmentPlanSource"] = tp_source
    try:
        from automation_registry import record_job_run

        record_job_run(
            "practice-exports",
            ok=bool(written),
            detail=f"written={len(written)}",
        )
    except Exception:
        pass
    return result


if __name__ == "__main__":
    import json as _json

    print(_json.dumps(sync_practice_exports(), indent=2))
