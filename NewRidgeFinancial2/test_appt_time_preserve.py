"""Preserve Sensei appt_time when daysheet/ODBC upserts with empty time."""

from __future__ import annotations

import sqlite3


def _seed(conn: sqlite3.Connection) -> None:
    from softdent_odbc_extract import ensure_sd_schema

    ensure_sd_schema(conn)
    conn.execute(
        """
        INSERT INTO sd_appointments
        (practice_id, patient_id, appt_date, provider_code, status, appt_time, extracted_at)
        VALUES ('','P1','2026-07-16','1','scheduled','09:30','t0')
        """
    )
    conn.commit()


def test_upsert_preserves_existing_appt_time():
    from softdent_odbc_extract import _upsert_sd_appointment

    conn = sqlite3.connect(":memory:")
    _seed(conn)
    _upsert_sd_appointment(
        conn,
        practice_id="",
        patient_id="P1",
        appt_date="2026-07-16",
        provider_code="1",
        status="seen",
        appt_time="",
        extracted_at="t1",
    )
    row = conn.execute(
        "SELECT status, appt_time FROM sd_appointments WHERE patient_id='P1'"
    ).fetchone()
    assert row[0] == "scheduled"  # do not clobber with daysheet 'seen'
    assert row[1] == "09:30"


def test_upsert_accepts_new_time():
    from softdent_odbc_extract import _upsert_sd_appointment

    conn = sqlite3.connect(":memory:")
    _seed(conn)
    _upsert_sd_appointment(
        conn,
        practice_id="",
        patient_id="P1",
        appt_date="2026-07-16",
        provider_code="1",
        status="checked-in",
        appt_time="10:15",
        extracted_at="t2",
    )
    row = conn.execute(
        "SELECT status, appt_time FROM sd_appointments WHERE patient_id='P1'"
    ).fetchone()
    assert row[0] == "checked-in"
    assert row[1] == "10:15"
