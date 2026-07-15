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


def _conn_has_operational_data(conn: sqlite3.Connection) -> bool:
    for table in ("sd_procedures", "sd_payments", "sd_patients", "sd_claims"):
        if not _table_exists(conn, table):
            continue
        cur = conn.cursor()
        # Table names are fixed literals above (not user input).
        cur.execute("SELECT COUNT(*) FROM " + table)
        if int(cur.fetchone()[0] or 0) > 0:
            return True
    for table in ("daysheet_totals", "production_by_provider", "transactions", "writeoff_totals", "production_by_ada"):
        if not _table_exists(conn, table):
            continue
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM " + table)
        if int(cur.fetchone()[0] or 0) > 0:
            return True
    return False


def _connect():
    conn, db_path = _open_db()
    if not conn:
        return None, db_path
    if not _conn_has_operational_data(conn):
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
        rows: list[tuple[str, float]] = []
        source = "sd_payments"
        if _table_exists(conn, "sd_payments"):
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
    conn, db_path = _open_db()
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
        source = "sd_appointments"
        if not appointments:
            cur.execute(
                """
                SELECT proc_date, patient_id, provider_code, 'seen'
                FROM sd_procedures
                WHERE COALESCE(patient_id, '') != '' AND COALESCE(proc_date, '') != ''
                GROUP BY proc_date, patient_id, provider_code
                ORDER BY proc_date DESC
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
            if appointments:
                source = "sd_procedures"
    finally:
        conn.close()
    return {"hasData": bool(appointments), "appointments": appointments, "source": source, "dbPath": str(db_path)}


def _hash_patient_id(patient_id: str) -> str:
    """PHI-safe 4-char hash for OM widgets (Moonshot OM-A0)."""
    import hashlib

    raw = str(patient_id or "").strip()
    if not raw:
        return "——"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:4].upper()


def _normalize_appt_status(raw: str) -> str:
    r = str(raw or "").lower()
    if any(x in r for x in ("cancel", "no show", "noshow", "broken")):
        return "open"
    if any(x in r for x in ("complete", "seen", "checkout", "checked out")):
        return "completed"
    if any(x in r for x in ("checkin", "check-in", "here", "arrived")):
        return "checked-in"
    if "block" in r:
        return "blocked"
    return "booked"


def appointments_today_snapshot(*, target_date: str | None = None) -> dict[str, Any]:
    """Today's SoftDent appointments grouped for OM operatory board (read-only).

    Uses real sd_appointments columns (appt_date, patient_id, provider_code, status)
    via softdent_practice_exports._build_operatory_from_sd_appointments — no invented
    operatory/time schema. Patient display is hashed (PHI-safe).
    """
    from datetime import date

    from softdent_practice_exports import _build_operatory_from_sd_appointments

    target = (target_date or date.today().isoformat())[:10]
    conn, db_path = _open_db()
    if not conn:
        return {
            "hasData": False,
            "operatories": [],
            "date": target,
            "count": 0,
            "source": "none",
        }
    try:
        chairs = _build_operatory_from_sd_appointments(conn, schedule_date=target, days_window=0)
        if not chairs:
            return {
                "hasData": False,
                "operatories": [],
                "date": target,
                "count": 0,
                "source": "sd_appointments",
                "dbPath": str(db_path),
                "emptyMessage": "No SoftDent appointments for today — run SoftDent sync.",
            }
        chosen_day = str(chairs[0].get("scheduleDate") or target)[:10]
        operatories: list[dict[str, Any]] = []
        total = 0
        for chair in chairs[:8]:
            slots_out: list[dict[str, Any]] = []
            for slot in (chair.get("slots") or [])[:12]:
                if not isinstance(slot, dict):
                    continue
                patient_raw = str(slot.get("patient") or "").strip()
                status = _normalize_appt_status(str(slot.get("procedure") or slot.get("tone") or ""))
                # procedure field holds status label from builder; tone is visual
                if slot.get("tone") == "ok":
                    status = "checked-in"
                slots_out.append(
                    {
                        "time": str(slot.get("time") or "—")[:5],
                        "status": status,
                        "patientHash": _hash_patient_id(patient_raw) if patient_raw else None,
                        "provider": str(chair.get("name") or ""),
                    }
                )
                total += 1
            operatories.append({"name": str(chair.get("name") or "Op—"), "slots": slots_out})
        return {
            "hasData": total > 0,
            "operatories": operatories,
            "date": chosen_day,
            "count": total,
            "source": "sd_appointments",
            "dbPath": str(db_path),
        }
    finally:
        conn.close()


def _initials_from_name(raw_name: str) -> str:
    parts = [x for x in str(raw_name or "").split() if x]
    letters = "".join(p[0] for p in parts[:2] if p).upper()
    return f"{letters or 'P'}—"


def appointments_range_snapshot(
    start_iso: str,
    days: int = 4,
    *,
    provider_filter: str | None = None,
) -> dict[str, Any]:
    """Multi-day appointment list for OM (Mon–Thu). PHI-safe hashes. SoftDent read-only.

    Real sd_appointments columns only (no appt_time). sd_patients uses patient_name
    (not first_name/last_name). Time displays as '—' honestly.
    """
    from datetime import datetime, timedelta

    conn, db_path = _open_db()
    if not conn:
        return {"hasData": False, "days": [], "source": "none", "dbPath": str(db_path) if db_path else None}

    try:
        if not _table_exists(conn, "sd_appointments"):
            return {
                "hasData": False,
                "days": [],
                "source": "none",
                "dbPath": str(db_path),
                "emptyMessage": "sd_appointments table missing — run SoftDent extract.",
            }

        start_raw = str(start_iso or "")[:10]
        try:
            start_dt = datetime.fromisoformat(start_raw)
        except ValueError:
            return {"hasData": False, "days": [], "source": "none", "error": "invalid start date"}

        day_count = max(1, min(int(days or 4), 14))
        dates = [(start_dt + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(day_count)]
        placeholders = ",".join("?" * len(dates))
        # Normalize date compare: SoftDent may store YYYY-MM-DD or with time suffix
        sql = f"""
        SELECT a.appt_date, a.patient_id, a.provider_code, a.status, p.patient_name
        FROM sd_appointments a
        LEFT JOIN sd_patients p ON a.patient_id = p.patient_id
        WHERE substr(replace(a.appt_date, '/', '-'), 1, 10) IN ({placeholders})
        ORDER BY a.appt_date, a.provider_code
        """
        params: list[Any] = list(dates)
        if provider_filter:
            sql = sql.replace(
                f"WHERE substr(replace(a.appt_date, '/', '-'), 1, 10) IN ({placeholders})",
                f"WHERE substr(replace(a.appt_date, '/', '-'), 1, 10) IN ({placeholders})"
                " AND COALESCE(a.provider_code,'') = ?",
            )
            params.append(str(provider_filter))

        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()

        days_out: list[dict[str, Any]] = []
        for d in dates:
            day_rows = [r for r in rows if str(r[0] or "")[:10].replace("/", "-") == d]
            slots: list[dict[str, Any]] = []
            for r in day_rows:
                patient_raw = str(r[4] or "").strip()
                slots.append(
                    {
                        "patientId": str(r[1] or ""),
                        "patientHash": _hash_patient_id(str(r[1] or "")),
                        "initials": _initials_from_name(patient_raw) if patient_raw else "P—",
                        "provider": str(r[2] or "") or "—",
                        "status": _normalize_appt_status(str(r[3] or "")),
                        "time": "—",  # SoftDent schema lacks time; honest placeholder
                        "procedureHint": "—",
                    }
                )
            days_out.append(
                {
                    "date": d,
                    "dayName": datetime.fromisoformat(d).strftime("%a"),
                    "slots": slots,
                    "count": len(slots),
                    "emptyMessage": f"No SoftDent appointments for {d}." if not slots else "",
                }
            )

        return {
            "hasData": any(d["count"] > 0 for d in days_out),
            "days": days_out,
            "dateRange": f"{dates[0]} to {dates[-1]}",
            "source": "sd_appointments",
            "dbPath": str(db_path),
            "emptyMessage": "No appointments found for Mon–Thu — verify SoftDent sync.",
        }
    finally:
        conn.close()


def monday_of_week_iso(ref_iso: str | None = None) -> str:
    """ISO date for Monday of the week containing ref (default: today)."""
    from datetime import date, datetime, timedelta

    if ref_iso:
        try:
            d = datetime.fromisoformat(str(ref_iso)[:10]).date()
        except ValueError:
            d = date.today()
    else:
        d = date.today()
    monday = d - timedelta(days=d.weekday())
    return monday.isoformat()


def provider_utilization_last_7d() -> dict[str, Any]:
    """Appointment counts by provider for the last 7 calendar days (read-only)."""
    from datetime import date, timedelta

    end = date.today()
    start = end - timedelta(days=6)
    conn, db_path = _open_db()
    if not conn:
        return {
            "hasData": False,
            "providers": [],
            "days": 7,
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
        }
    try:
        if not _table_exists(conn, "sd_appointments"):
            return {
                "hasData": False,
                "providers": [],
                "days": 7,
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "dbPath": str(db_path),
            }
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COALESCE(provider_code, 'unassigned') AS provider,
                   COUNT(*) AS appt_count
            FROM sd_appointments
            WHERE substr(replace(appt_date, '/', '-'), 1, 10) >= ?
              AND substr(replace(appt_date, '/', '-'), 1, 10) <= ?
            GROUP BY COALESCE(provider_code, 'unassigned')
            ORDER BY appt_count DESC
            LIMIT 12
            """,
            (start.isoformat(), end.isoformat()),
        )
        providers = [
            {"providerCode": str(row[0] or "unassigned"), "appointments": int(row[1] or 0)}
            for row in cur.fetchall()
        ]
    finally:
        conn.close()
    return {
        "hasData": bool(providers),
        "providers": providers,
        "days": 7,
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "source": "sd_appointments",
        "dbPath": str(db_path),
    }


def claims_outstanding(*, limit: int = 10) -> dict[str, Any]:
    """Open SoftDent claims sample + full outstanding total (empty ≠ $0).

    ``limit`` caps the returned claim *list* only — totalOutstanding/count
    always cover the full open set so UI dollars are not understated.
    """
    conn, db_path = _connect()
    if not conn:
        return {
            "hasData": False,
            "claims": [],
            "totalOutstanding": None,
            "count": 0,
            "honesty": "empty != $0",
        }
    try:
        cur = conn.cursor()
        source = "sd_claims"
        open_where = """
            COALESCE(claim_amount, 0) > 0
              AND UPPER(COALESCE(claim_status, '')) NOT IN ('PAID', 'CLOSED', 'DENIED')
        """
        total = None
        count = 0
        if _table_exists(conn, "sd_claims"):
            cur.execute(
                "SELECT COUNT(*), SUM(COALESCE(claim_amount, 0)) FROM sd_claims WHERE " + open_where
            )
            row = cur.fetchone() or (0, None)
            count = int(row[0] or 0)
            if row[1] is not None:
                total = round(float(row[1]), 2)
            cur.execute(
                """
                SELECT claim_id, patient_name, payer, service_date, claim_amount, claim_status
                FROM sd_claims
                WHERE """
                + open_where
                + """
                ORDER BY claim_amount DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            )
            rows = cur.fetchall()
        else:
            rows = []

        if not rows and _table_exists(conn, "outstanding_claims"):
            source = "outstanding_claims"
            cur.execute(
                """
                SELECT COUNT(*), SUM(COALESCE(claim_amount, 0))
                FROM outstanding_claims
                WHERE COALESCE(claim_amount, 0) > 0
                """
            )
            row = cur.fetchone() or (0, None)
            count = int(row[0] or 0)
            if row[1] is not None:
                total = round(float(row[1]), 2)
            cur.execute(
                """
                SELECT claim_id, patient_name, payer, service_date, claim_amount, claim_status
                FROM outstanding_claims
                WHERE COALESCE(claim_amount, 0) > 0
                ORDER BY claim_amount DESC
                LIMIT ?
                """,
                (max(1, int(limit)),),
            )
            rows = cur.fetchall()

        claims = []
        for claim_id, patient, payer, service_date, amount, status in rows:
            claims.append(
                {
                    "claimId": str(claim_id or ""),
                    "patientName": str(patient or ""),
                    "payer": str(payer or ""),
                    "serviceDate": str(service_date or ""),
                    "amount": round(float(amount or 0), 2),
                    "status": str(status or ""),
                }
            )
    finally:
        conn.close()
    return {
        "hasData": count > 0 or bool(claims),
        "claims": claims,
        "totalOutstanding": total,
        "count": count,
        "sampleLimit": max(1, int(limit)),
        "source": source,
        "dbPath": str(db_path),
        "honesty": "empty != $0",
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


def _parse_ar_money(value: Any) -> float | None:
    raw = str(value or "").replace("$", "").replace(",", "").strip()
    if not raw or raw in {"—", "-", "N/A", "na", "null"}:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _normalize_ar_bucket_label(label: str) -> str:
    low = label.strip().lower().replace("–", "-")
    if low in {"current", "0-30", "net 30", "current balance"}:
        return "0-30"
    if low in {"31-60", "30-60"} or low.startswith("31") or "31-60" in low:
        return "31-60"
    if low in {"61-90", "60-90"} or low.startswith("61") or "61-90" in low:
        return "61-90"
    if low in {"90+", "91+", "90-plus", "120+"} or low.startswith("90") or low.startswith("120"):
        return "90+"
    return label.strip() or "Unknown"


def ar_aging() -> dict[str, Any]:
    """SoftDent A/R bucket totals from import cache CSV (empty ≠ $0 · read-only)."""
    import csv
    from pathlib import Path

    from import_loader import softdent_import_dir

    empty: dict[str, Any] = {
        "hasData": False,
        "buckets": [],
        "source": "softdent_ar_aging.csv",
        "honesty": "empty != $0",
    }
    candidates = [
        softdent_import_dir() / "softdent_ar_aging.csv",
        softdent_import_dir() / "softdent_ar_aging.json",
    ]
    path: Path | None = next((p for p in candidates if p.is_file()), None)
    if path is None:
        empty["error"] = "missing"
        return empty

    buckets: list[dict[str, Any]] = []
    try:
        if path.suffix.lower() == ".json":
            import json

            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            rows = payload if isinstance(payload, list) else (payload.get("rows") if isinstance(payload, dict) else [])
            for row in rows if isinstance(rows, list) else []:
                if not isinstance(row, dict):
                    continue
                amt = _parse_ar_money(row.get("Balance") or row.get("balance") or row.get("amount"))
                if amt is None:
                    continue
                label = _normalize_ar_bucket_label(str(row.get("Bucket") or row.get("bucket") or "Unknown"))
                buckets.append({"bucket": label, "amount": round(amt, 2)})
        else:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    if not isinstance(row, dict):
                        continue
                    amt = _parse_ar_money(row.get("Balance") or row.get("balance") or row.get("Amount"))
                    if amt is None:
                        continue
                    label = _normalize_ar_bucket_label(str(row.get("Bucket") or row.get("bucket") or "Unknown"))
                    buckets.append({"bucket": label, "amount": round(amt, 2)})
    except Exception as exc:
        empty["error"] = str(exc)
        return empty

    if not buckets:
        empty["error"] = "empty_file"
        empty["path"] = str(path)
        return empty

    # Merge duplicate labels (Current + 0-30) without inventing missing buckets.
    merged: dict[str, float] = {}
    order: list[str] = []
    for item in buckets:
        key = str(item["bucket"])
        if key not in merged:
            order.append(key)
            merged[key] = 0.0
        merged[key] += float(item["amount"])
    preferred = ["0-30", "31-60", "61-90", "90+"]
    ordered = [b for b in preferred if b in merged] + [b for b in order if b not in preferred]
    out_buckets = [{"bucket": b, "amount": round(merged[b], 2)} for b in ordered]
    total = round(sum(merged.values()), 2)
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age_hours = round((datetime.now(timezone.utc) - mtime).total_seconds() / 3600.0, 2)
    stale = age_hours > 24.0
    return {
        "hasData": True,
        "buckets": out_buckets,
        "total": total,
        "source": path.name,
        "path": str(path),
        "mtime": mtime.replace(microsecond=0).isoformat(),
        "ageHours": age_hours,
        "stale": stale,
        "honesty": "empty != $0",
    }
