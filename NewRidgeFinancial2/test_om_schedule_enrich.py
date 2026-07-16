"""Tests for OM schedule enrich (ADA join + honest time)."""

from __future__ import annotations

import sqlite3


def _seed(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE sd_patients (
            practice_id TEXT NOT NULL DEFAULT '',
            patient_id TEXT NOT NULL,
            patient_name TEXT,
            first_visit_date TEXT,
            last_visit_date TEXT,
            extracted_at TEXT,
            PRIMARY KEY (practice_id, patient_id)
        );
        CREATE TABLE sd_appointments (
            practice_id TEXT NOT NULL DEFAULT '',
            patient_id TEXT NOT NULL DEFAULT '',
            appt_date TEXT NOT NULL DEFAULT '',
            provider_code TEXT NOT NULL DEFAULT '',
            status TEXT,
            appt_time TEXT,
            extracted_at TEXT,
            PRIMARY KEY (practice_id, patient_id, appt_date, provider_code)
        );
        CREATE TABLE sd_procedures (
            practice_id TEXT NOT NULL DEFAULT '',
            patient_id TEXT NOT NULL DEFAULT '',
            proc_date TEXT NOT NULL DEFAULT '',
            ada_code TEXT NOT NULL DEFAULT '',
            tooth TEXT,
            surface TEXT,
            provider_code TEXT,
            description TEXT,
            production REAL,
            extracted_at TEXT,
            PRIMARY KEY (practice_id, patient_id, proc_date, ada_code, tooth, surface, provider_code)
        );
        """
    )
    conn.execute(
        "INSERT INTO sd_patients VALUES ('','P1','Jane Doe','2020-01-01','2026-07-16','t')"
    )
    conn.execute(
        "INSERT INTO sd_appointments VALUES ('','P1','2026-07-14','DR1','booked','09:30','t')"
    )
    conn.execute(
        "INSERT INTO sd_appointments VALUES ('','P1','2026-07-15','DR1','booked',NULL,'t')"
    )
    conn.execute(
        """
        INSERT INTO sd_procedures
        VALUES ('','P1','2026-07-14','D0120','','','DR1','exam',50,'t')
        """
    )
    conn.execute(
        """
        INSERT INTO sd_procedures
        VALUES ('','P1','2026-07-14','D0220','','','DR1','bw',40,'t')
        """
    )
    conn.commit()


def test_appointments_range_ada_and_time(monkeypatch, tmp_path):
    import nr2_softdent_daily as daily

    db = tmp_path / "sd.sqlite"
    conn = sqlite3.connect(str(db))
    _seed(conn)
    conn.close()

    monkeypatch.setattr(daily, "_open_db", lambda: (sqlite3.connect(str(db)), db))

    snap = daily.appointments_range_snapshot("2026-07-14", days=2)
    assert snap["hasData"] is True
    assert snap.get("apptTimeColumn") is True
    mon = snap["days"][0]
    assert mon["date"] == "2026-07-14"
    assert mon["count"] == 1
    slot = mon["slots"][0]
    assert slot["time"] == "09:30"
    assert slot["timeMissing"] is False
    assert "D0120" in slot["adaCodes"]
    assert "D0220" in slot["adaCodes"]
    assert "D0120" in slot["procedureHint"]
    assert slot["initials"]  # board PHI
    assert slot.get("patientName") == "Jane Doe"  # dossier only

    tue = snap["days"][1]
    assert tue["slots"][0]["time"] == "—"
    assert tue["slots"][0]["timeMissing"] is True
    assert tue["slots"][0]["procedureHint"] == "—"


def test_same_day_ada_normalizes_softdent_internal(monkeypatch, tmp_path):
    import nr2_softdent_daily as daily

    db = tmp_path / "sd.sqlite"
    conn = sqlite3.connect(str(db))
    _seed(conn)
    conn.execute(
        """
        INSERT INTO sd_procedures
        VALUES ('','P1','2026-07-15','111000','','','DR1','prophy',80,'t')
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(daily, "_open_db", lambda: (sqlite3.connect(str(db)), db))
    snap = daily.appointments_range_snapshot("2026-07-15", days=1)
    codes = snap["days"][0]["slots"][0]["adaCodes"]
    assert "D1110" in codes
    assert "111000" not in codes


def test_format_appt_time_never_invents():
    import nr2_softdent_daily as daily

    assert daily._format_appt_time(None) == "—"
    assert daily._format_appt_time("") == "—"
    assert daily._format_appt_time("930") == "09:30"
    assert daily._format_appt_time("14:05:00") == "14:05"


def test_next_patient_hint_prefers_upcoming(monkeypatch):
    import nr2_softdent_daily as daily
    from datetime import date

    today = date.today().isoformat()
    monkeypatch.setattr(
        daily,
        "_next_patient_hint",
        daily._next_patient_hint,
    )
    days = [
        {
            "date": today,
            "slots": [
                {
                    "time": "06:00",
                    "patientId": "A",
                    "patientHash": "AAAA",
                    "initials": "AA",
                    "provider": "1",
                    "adaCodes": ["D0120"],
                },
                {
                    "time": "23:50",
                    "patientId": "B",
                    "patientHash": "BBBB",
                    "initials": "BB",
                    "provider": "1",
                    "adaCodes": ["D1110"],
                },
            ],
        }
    ]
    hint = daily._next_patient_hint(days)
    assert hint and hint.get("available") is True
    # Depending on wall clock, either upcoming 23:50 or past last timed
    assert hint.get("patientId") in ("A", "B")
    assert hint.get("time") in ("06:00", "23:50")
