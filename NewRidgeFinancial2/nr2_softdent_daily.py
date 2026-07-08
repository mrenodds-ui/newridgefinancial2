"""SoftDent daily operational widgets from sd_* tables (hal-10071)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from softdent_practice_exports import NEW_PATIENT_PROCEDURE_CODES
from softdent_odbc_extract import resolve_sd_sqlite_db, table_row_counts

NEW_PATIENT_CODES = NEW_PATIENT_PROCEDURE_CODES


def _utc_now_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def _open_db():
    db_path = resolve_sd_sqlite_db()
    if not db_path or not db_path.is_file():
        return None, db_path
    return sqlite3.connect(db_path), db_path


def _connect():
    conn, db_path = _open_db()
    if not conn:
        return None, db_path
    counts = table_row_counts(db_path)
    if sum(int(counts.get(table) or 0) for table in ("sd_procedures", "sd_payments", "sd_patients", "sd_claims")) <= 0:
        conn.close()
        return None, db_path
    return conn, db_path


def _collections_from_daysheet_totals(conn: sqlite3.Connection, *, limit: int) -> list[tuple[str, float]]:
    if not _table_exists(conn, "daysheet_totals"):
        return []
    cur = conn.cursor()
    cur.execute(
        """
        SELECT year_month, SUM(COALESCE(collections, 0))
        FROM daysheet_totals
        WHERE COALESCE(collections, 0) > 0
        GROUP BY year_month
        ORDER BY year_month
        """
    )
    rows = [(str(period), float(total or 0)) for period, total in cur.fetchall() if period]
    return rows[-limit:]


def _provider_production_from_analytics(conn: sqlite3.Connection, *, limit: int) -> list[dict[str, Any]]:
    if not _table_exists(conn, "production_by_provider"):
        return []
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COALESCE(provider_name, provider_label, provider_id), SUM(COALESCE(gross_production, 0)) AS total
        FROM production_by_provider
        WHERE COALESCE(gross_production, 0) > 0
        GROUP BY COALESCE(provider_name, provider_label, provider_id)
        ORDER BY total DESC
        LIMIT ?
        """,
        (limit,),
    )
    providers: list[dict[str, Any]] = []
    for label, total in cur.fetchall():
        providers.append({"providerCode": str(label or "").strip() or "unknown", "production": round(float(total or 0), 2)})
    return providers


def collections_daily(*, limit: int = 30) -> dict[str, Any]:
    conn, db_path = _open_db()
    if not conn:
        return {"hasData": False, "points": [], "labels": [], "values": []}
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT payment_date, SUM(COALESCE(amount, 0))
            FROM sd_payments
            WHERE payment_date IS NOT NULL AND payment_date != '' AND COALESCE(amount, 0) > 0
            GROUP BY payment_date
            ORDER BY payment_date
            """
        )
        rows = [(str(day), float(total or 0)) for day, total in cur.fetchall() if day]
        source = "sd_payments"
        if not rows:
            rows = _collections_from_daysheet_totals(conn, limit=limit)
            source = "daysheet_totals"
    finally:
        conn.close()
    trimmed = rows[-limit:]
    return {
        "hasData": bool(trimmed),
        "labels": [day for day, _ in trimmed],
        "values": [round(total, 2) for _, total in trimmed],
        "points": [{"date": day, "collections": round(total, 2)} for day, total in trimmed],
        "source": source,
        "dbPath": str(db_path),
    }


def new_patients_mtd(*, period: str | None = None) -> dict[str, Any]:
    period = (period or _utc_now_month())[:7]
    conn, db_path = _connect()
    if not conn:
        return {"hasData": False, "count": 0, "period": period}
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(DISTINCT patient_id)
            FROM sd_patients
            WHERE substr(COALESCE(first_visit_date, ''), 1, 7) = ?
            """,
            (period,),
        )
        count = int(cur.fetchone()[0] or 0)
        if count <= 0:
            cur.execute(
                """
                SELECT COUNT(DISTINCT patient_id)
                FROM sd_procedures
                WHERE substr(proc_date, 1, 7) = ?
                  AND ada_code IN ({codes})
                """.format(codes=",".join("?" for _ in NEW_PATIENT_CODES)),
                (period, *NEW_PATIENT_CODES),
            )
            count = int(cur.fetchone()[0] or 0)
    finally:
        conn.close()
    return {"hasData": count > 0, "count": count, "period": period, "source": "sd_patients", "dbPath": str(db_path)}


def appointments_snapshot(*, limit: int = 12) -> dict[str, Any]:
    conn, db_path = _connect()
    if not conn:
        return {"hasData": False, "appointments": []}
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT appt_date, patient_id, provider_code, status
            FROM sd_appointments
            ORDER BY appt_date DESC
            LIMIT ?
            """,
            (limit,),
        )
        appointments = [
            {
                "date": str(row[0] or ""),
                "patientId": str(row[1] or ""),
                "provider": str(row[2] or ""),
                "status": str(row[3] or ""),
            }
            for row in cur.fetchall()
        ]
    finally:
        conn.close()
    return {"hasData": bool(appointments), "appointments": appointments, "source": "sd_appointments", "dbPath": str(db_path)}


def claims_outstanding(*, limit: int = 10) -> dict[str, Any]:
    conn, db_path = _connect()
    if not conn:
        return {"hasData": False, "claims": [], "totalOutstanding": 0}
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT claim_id, patient_name, payer, service_date, claim_amount, claim_status
            FROM sd_claims
            WHERE COALESCE(claim_amount, 0) > 0
              AND UPPER(COALESCE(claim_status, '')) NOT IN ('PAID', 'CLOSED', 'DENIED')
            ORDER BY claim_amount DESC
            LIMIT ?
            """,
            (limit,),
        )
        claims = []
        total = 0.0
        for claim_id, patient, payer, service_date, amount, status in cur.fetchall():
            amt = float(amount or 0)
            total += amt
            claims.append(
                {
                    "claimId": str(claim_id or ""),
                    "patientName": str(patient or ""),
                    "payer": str(payer or ""),
                    "serviceDate": str(service_date or ""),
                    "amount": round(amt, 2),
                    "status": str(status or ""),
                }
            )
        if not claims and _table_exists(conn, "outstanding_claims"):
            cur.execute(
                """
                SELECT claim_id, patient_name, payer, service_date, claim_amount, claim_status
                FROM outstanding_claims
                WHERE COALESCE(claim_amount, 0) > 0
                ORDER BY claim_amount DESC
                LIMIT ?
                """,
                (limit,),
            )
            for claim_id, patient, payer, service_date, amount, status in cur.fetchall():
                amt = float(amount or 0)
                total += amt
                claims.append(
                    {
                        "claimId": str(claim_id or ""),
                        "patientName": str(patient or ""),
                        "payer": str(payer or ""),
                        "serviceDate": str(service_date or ""),
                        "amount": round(amt, 2),
                        "status": str(status or ""),
                    }
                )
    finally:
        conn.close()
    return {
        "hasData": bool(claims),
        "claims": claims,
        "totalOutstanding": round(total, 2),
        "source": "sd_claims",
        "dbPath": str(db_path),
    }


def provider_production(*, limit: int = 8) -> dict[str, Any]:
    conn, db_path = _open_db()
    if not conn:
        return {"hasData": False, "providers": []}
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT provider_code, SUM(COALESCE(production, 0)) AS total
            FROM sd_procedures
            WHERE COALESCE(production, 0) > 0
            GROUP BY provider_code
            ORDER BY total DESC
            LIMIT ?
            """,
            (limit,),
        )
        providers = [
            {"providerCode": str(code or ""), "production": round(float(total or 0), 2)}
            for code, total in cur.fetchall()
        ]
        source = "sd_procedures"
        if not providers:
            providers = _provider_production_from_analytics(conn, limit=limit)
            source = "production_by_provider"
    finally:
        conn.close()
    grand = round(sum(item["production"] for item in providers), 2)
    return {"hasData": bool(providers), "providers": providers, "total": grand, "source": source, "dbPath": str(db_path)}


def adjustment_log(*, limit: int = 10) -> dict[str, Any]:
    conn, db_path = _open_db()
    if not conn:
        return {"hasData": False, "adjustments": []}
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT adj_date, patient_id, ada_code, amount, description
            FROM sd_adjustments
            ORDER BY adj_date DESC
            LIMIT ?
            """,
            (limit,),
        )
        adjustments = [
            {
                "date": str(row[0] or ""),
                "patientId": str(row[1] or ""),
                "code": str(row[2] or ""),
                "amount": round(float(row[3] or 0), 2),
                "description": str(row[4] or ""),
            }
            for row in cur.fetchall()
        ]
        source = "sd_adjustments"
        if not adjustments and _table_exists(conn, "writeoff_totals"):
            cur.execute(
                """
                SELECT report_date, writeoff_type, amount
                FROM writeoff_totals
                WHERE COALESCE(amount, 0) != 0
                ORDER BY report_date DESC
                LIMIT ?
                """,
                (limit,),
            )
            for report_date, writeoff_type, amount in cur.fetchall():
                adjustments.append(
                    {
                        "date": str(report_date or ""),
                        "patientId": "",
                        "code": str(writeoff_type or "writeoff"),
                        "amount": round(abs(float(amount or 0)), 2),
                        "description": str(writeoff_type or "Write-off"),
                    }
                )
            source = "writeoff_totals"
    finally:
        conn.close()
    return {"hasData": bool(adjustments), "adjustments": adjustments, "source": source, "dbPath": str(db_path)}


def patient_retention(*, months: int = 6) -> dict[str, Any]:
    conn, db_path = _connect()
    if not conn:
        return {"hasData": False, "activePatients": 0, "returningRatePct": None}
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT patient_id) FROM sd_patients")
        active = int(cur.fetchone()[0] or 0)
        cur.execute(
            """
            SELECT COUNT(DISTINCT patient_id)
            FROM sd_appointments
            WHERE appt_date >= date('now', ?)
            """,
            (f"-{months * 30} days",),
        )
        recent = int(cur.fetchone()[0] or 0)
    finally:
        conn.close()
    rate = round((recent / active) * 100, 1) if active > 0 else None
    return {
        "hasData": active > 0,
        "activePatients": active,
        "recentVisits": recent,
        "returningRatePct": rate,
        "windowMonths": months,
        "source": "sd_patients+sd_appointments",
        "dbPath": str(db_path),
    }


def operatory_grid() -> dict[str, Any]:
    """Operatory chair grid from export file or sd_appointments-derived schedule."""
    from import_loader import softdent_import_dir
    from softdent_practice_exports import (
        _aggregate_operatory_from_db,
        _build_operatory_from_sd_appointments,
        _read_operatory_chairs_file,
    )

    op_path = softdent_import_dir() / "operatory_schedule.json"
    if op_path.is_file():
        chairs = _read_operatory_chairs_file(op_path)
        if chairs:
            return {
                "hasData": True,
                "operatoryChairs": chairs,
                "source": "operatory_schedule.json",
                "sourcePath": str(op_path),
            }

    conn, db_path = _open_db()
    if not conn:
        return {"hasData": False, "operatoryChairs": []}
    try:
        chairs = _aggregate_operatory_from_db(conn)
        if not chairs:
            chairs = _build_operatory_from_sd_appointments(conn)
        source = "analytics-db" if chairs else "none"
        if chairs and not op_path.is_file():
            source = "sd_appointments"
    finally:
        conn.close()
    return {
        "hasData": bool(chairs),
        "operatoryChairs": chairs or [],
        "source": source,
        "dbPath": str(db_path),
    }


def production_daily(*, limit: int = 30) -> dict[str, Any]:
    """Daily production series — sd_procedures with daysheet_totals fallback."""
    conn, db_path = _open_db()
    if not conn:
        return {"hasData": False, "points": [], "labels": [], "values": []}
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
        source = "sd_procedures"
        if not rows and _table_exists(conn, "daysheet_totals"):
            cur.execute(
                """
                SELECT year_month, SUM(COALESCE(gross_production, net_production, 0))
                FROM daysheet_totals
                WHERE COALESCE(gross_production, net_production, 0) > 0
                GROUP BY year_month
                ORDER BY year_month
                """
            )
            rows = [(str(period), float(total or 0)) for period, total in cur.fetchall() if period]
            source = "daysheet_totals"
    finally:
        conn.close()
    trimmed = rows[-limit:]
    return {
        "hasData": bool(trimmed),
        "labels": [day for day, _ in trimmed],
        "values": [round(total, 2) for _, total in trimmed],
        "points": [{"date": day, "production": round(total, 2)} for day, total in trimmed],
        "source": source,
        "dbPath": str(db_path),
    }
