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


def _connect():
    db_path = resolve_sd_sqlite_db()
    if not db_path or not db_path.is_file():
        return None, db_path
    counts = table_row_counts(db_path)
    if sum(int(counts.get(table) or 0) for table in ("sd_procedures", "sd_payments", "sd_patients", "sd_claims")) <= 0:
        return None, db_path
    return sqlite3.connect(db_path), db_path


def collections_daily(*, limit: int = 30) -> dict[str, Any]:
    conn, db_path = _connect()
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
    finally:
        conn.close()
    trimmed = rows[-limit:]
    return {
        "hasData": bool(trimmed),
        "labels": [day for day, _ in trimmed],
        "values": [round(total, 2) for _, total in trimmed],
        "points": [{"date": day, "collections": round(total, 2)} for day, total in trimmed],
        "source": "sd_payments",
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
    conn, db_path = _connect()
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
    finally:
        conn.close()
    grand = round(sum(item["production"] for item in providers), 2)
    return {"hasData": bool(providers), "providers": providers, "total": grand, "source": "sd_procedures", "dbPath": str(db_path)}


def adjustment_log(*, limit: int = 10) -> dict[str, Any]:
    conn, db_path = _connect()
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
    finally:
        conn.close()
    return {"hasData": bool(adjustments), "adjustments": adjustments, "source": "sd_adjustments", "dbPath": str(db_path)}


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
