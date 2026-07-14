"""Tests for SoftDent ODBC extract lane (hal-10070)."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from softdent_odbc_extract import (
    ensure_sd_schema,
    ensure_softdent_odbc_fresh,
    extract_softdent_odbc,
    odbc_configured,
    read_extract_status,
    table_row_counts,
)


def _sample_daysheet(path: Path) -> None:
    payload = {
        "normalized": {"report_date": "2026-06-15"},
        "raw_row": {
            "formatted_report_rows": [
                ["Daysheet", "", "", "", "", "", "Daysheet", "", "", "", "", "", "", "", ""],
                ["", "ID", "Name", "", "", "", "", "", "", "", "", "", "", "", ""],
                ["June 15, 2026", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
                ["", "1001", "Jane Doe", "", "DR1", "1110", "Prophylaxis - Adult", "120.00", "", "", "", "", "", "", ""],
                ["", "1002", "John Smith", "", "DR1", "2", "Insurance Check Payment", "", "", "($50.00)", "", "$85.00", "", "", ""],
                ["", "1003", "Pat Lee", "", "DR1", "51", "Insurance Co Write-Off", "", "", "($40.00)", "", "", "", "", ""],
            ]
        },
    }
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _sample_claims(path: Path) -> None:
    path.write_text(
        "ClaimId,PatientName,Payer,ServiceDate,ClaimAmount,ClaimStatus\n"
        "CLM-001,Jane Doe,Delta Dental,2026-06-10,420.00,Ready\n",
        encoding="utf-8",
    )


def _sample_sensei_root(path: Path) -> None:
    ref = path / "Reference"
    ref.mkdir(parents=True)
    (ref / "patient_1001.json").write_text(
        json.dumps(
            {
                "PATIENT": {
                    "Id": 1001,
                    "UniqueID": 1001,
                    "Firstname": "Jane",
                    "Lastname": "Doe",
                    "FirstVisit": "2020/01/15",
                    "LastVisit": "2026/06/01",
                }
            }
        ),
        encoding="utf-8",
    )
    (ref / "dentist_1.json").write_text(
        json.dumps({"DENTIST": {"Id": 1, "Firstname": "Michael", "Lastname": "Reno"}}),
        encoding="utf-8",
    )
    (ref / "appointment_9001.json").write_text(
        json.dumps(
            {
                "APPTS": {
                    "PatUniqueID": 1001,
                    "Date": "2026/06/15",
                    "Dr": 1,
                    "CheckedIn": "09:30",
                    "Proc0_Code": "1110",
                    "Proc0_Fee": "120.00",
                }
            }
        ),
        encoding="utf-8",
    )


def _patch_no_sensei():
    return patch("softdent_odbc_extract.resolve_sensei_datasync_root", return_value=None)


class SoftdentOdbcExtractTests(unittest.TestCase):
    def test_odbc_not_configured_by_default(self) -> None:
        with patch("softdent_odbc_extract.odbc_dsn", return_value=""):
            self.assertFalse(odbc_configured())

    def test_json_fallback_populates_sd_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analytics.sqlite3"
            daysheet = Path(tmp) / "daysheet.jsonl"
            claims = Path(tmp) / "softdent_claims_export.csv"
            _sample_daysheet(daysheet)
            _sample_claims(claims)
            with _patch_no_sensei(), patch("softdent_odbc_extract.resolve_sd_sqlite_db", return_value=db_path), patch(
                "softdent_odbc_extract._resolve_daysheet_path", return_value=daysheet
            ), patch("softdent_odbc_extract._resolve_claims_path", return_value=claims):
                result = extract_softdent_odbc(force=True)
            self.assertTrue(result["ok"])
            self.assertEqual(result["mode"], "json-fallback")
            counts = table_row_counts(db_path)
            self.assertGreater(counts["sd_procedures"], 0)
            self.assertGreater(counts["sd_patients"], 0)
            self.assertGreater(counts["sd_claims"], 0)
            self.assertGreaterEqual(counts["sd_payments"], 1)
            self.assertGreaterEqual(counts["sd_adjustments"], 1)

    def test_sensei_datasync_populates_sd_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analytics.sqlite3"
            sensei_root = Path(tmp) / "sensei"
            _sample_sensei_root(sensei_root)
            with patch("softdent_odbc_extract.resolve_sd_sqlite_db", return_value=db_path), patch(
                "softdent_odbc_extract.resolve_sensei_datasync_root", return_value=sensei_root
            ), patch("softdent_odbc_extract._resolve_daysheet_path", return_value=None), patch(
                "softdent_odbc_extract._resolve_register_path", return_value=None
            ), patch("softdent_odbc_extract._resolve_claims_path", return_value=Path("")):
                result = extract_softdent_odbc(force=True)
            self.assertTrue(result["ok"])
            self.assertEqual(result["mode"], "sensei-datasync")
            counts = table_row_counts(db_path)
            self.assertEqual(counts["sd_patients"], 1)
            self.assertEqual(counts["sd_providers"], 1)
            self.assertEqual(counts["sd_appointments"], 1)
            self.assertEqual(counts["sd_procedures"], 1)

    def test_sensei_plus_json_fallback_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analytics.sqlite3"
            daysheet = Path(tmp) / "daysheet.jsonl"
            sensei_root = Path(tmp) / "sensei"
            _sample_daysheet(daysheet)
            _sample_sensei_root(sensei_root)
            with patch("softdent_odbc_extract.resolve_sd_sqlite_db", return_value=db_path), patch(
                "softdent_odbc_extract.resolve_sensei_datasync_root", return_value=sensei_root
            ), patch("softdent_odbc_extract._resolve_daysheet_path", return_value=daysheet), patch(
                "softdent_odbc_extract._resolve_claims_path", return_value=Path("")
            ):
                result = extract_softdent_odbc(force=True)
            self.assertEqual(result["mode"], "sensei+json-fallback")
            counts = table_row_counts(db_path)
            self.assertGreaterEqual(counts["sd_patients"], 1)
            self.assertGreaterEqual(counts["sd_payments"], 1)

    def test_register_jsonl_populates_payments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analytics.sqlite3"
            register = Path(tmp) / "register_for_period_2026-06-01_2026-06-15.jsonl"
            register.write_text(
                json.dumps(
                    {
                        "dataset_name": "register_for_period",
                        "raw_row": ["", "Cash", "125.50", "", "", "", "", "", "", ""],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with _patch_no_sensei(), patch("softdent_odbc_extract.resolve_sd_sqlite_db", return_value=db_path), patch(
                "softdent_odbc_extract._resolve_daysheet_path", return_value=None
            ), patch("softdent_odbc_extract._resolve_register_path", return_value=register), patch(
                "softdent_odbc_extract._resolve_claims_path", return_value=Path("")
            ):
                result = extract_softdent_odbc(force=True)
            self.assertTrue(result["refreshed"] or result["mode"] in ("json-fallback", "none"))
            counts = table_row_counts(db_path)
            self.assertGreaterEqual(counts["sd_payments"], 1)

    def test_odbc_lane_graceful_without_dsn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analytics.sqlite3"
            conn = sqlite3.connect(db_path)
            ensure_sd_schema(conn)
            conn.close()
            with _patch_no_sensei(), patch("softdent_odbc_extract.resolve_sd_sqlite_db", return_value=db_path), patch(
                "softdent_odbc_extract.odbc_dsn", return_value=""
            ), patch("softdent_odbc_extract._resolve_daysheet_path", return_value=None), patch(
                "softdent_odbc_extract._resolve_claims_path", return_value=Path("")
            ):
                result = extract_softdent_odbc(force=True)
            self.assertEqual(result["odbc"]["error"], "odbc_not_configured")
            self.assertFalse(result["ok"])

    def test_ensure_fresh_skips_when_recent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analytics.sqlite3"
            conn = sqlite3.connect(db_path)
            ensure_sd_schema(conn)
            conn.execute(
                "INSERT OR REPLACE INTO sd_extract_meta (key, value) VALUES ('last_extract_at', ?)",
                ("2099-01-01T00:00:00+00:00",),
            )
            conn.commit()
            conn.close()
            with patch("softdent_odbc_extract.resolve_sd_sqlite_db", return_value=db_path):
                result = ensure_softdent_odbc_fresh(max_age_minutes=60)
            self.assertFalse(result["stale"])
            self.assertFalse(result["refreshed"])
            self.assertIn("status", result)

    def test_read_extract_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analytics.sqlite3"
            daysheet = Path(tmp) / "daysheet.jsonl"
            _sample_daysheet(daysheet)
            with _patch_no_sensei(), patch("softdent_odbc_extract.resolve_sd_sqlite_db", return_value=db_path), patch(
                "softdent_odbc_extract._resolve_daysheet_path", return_value=daysheet
            ), patch("softdent_odbc_extract._resolve_claims_path", return_value=Path("")):
                extract_softdent_odbc(force=True)
            status = read_extract_status(db_path)
            self.assertEqual(status["lastMode"], "json-fallback")
            self.assertGreaterEqual(int(status["populatedTables"] or 0), 3)
            self.assertIn("nextSteps", status)
            self.assertIsInstance(status["nextSteps"], list)

    def test_read_extract_status_reports_query_config(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SOFTDENT_ODBC_DSN": "TestDSN",
                "SOFTDENT_ODBC_PATIENTS_QUERY": "SELECT 1 AS patient_id",
            },
            clear=False,
        ):
            with patch("softdent_odbc_extract.odbc_dsn", return_value="TestDSN"):
                status = read_extract_status(None)
        self.assertTrue(status["odbcConfigured"])
        self.assertGreaterEqual(status["queriesConfigured"], 1)
        self.assertIn("sd_patients", status["configuredQueryTables"])


class SoftDentInsuranceExtractTests(unittest.TestCase):
    """Moonshot SoftDent insurance extract (hal-10576)."""

    def test_insurance_schema_created(self) -> None:
        from softdent_odbc_extract import SD_TABLES, _table_exists

        conn = sqlite3.connect(":memory:")
        try:
            ensure_sd_schema(conn)
            self.assertTrue(_table_exists(conn, "sd_patient_insurance"))
            self.assertTrue(_table_exists(conn, "sd_carrier_payer_map"))
            self.assertIn("sd_patient_insurance", SD_TABLES)
        finally:
            conn.close()

    def test_insurance_csv_honest_nulls(self) -> None:
        from softdent_odbc_extract import load_insurance_csv

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "patient_insurance_20260711.csv"
            path.write_text(
                "PatientID,InsuranceCompany,PolicyNumber,GroupNumber,Priority\n"
                "P100,Delta Dental,,GRP1,1\n"
                "P200,MetLife,MEM999,GRP2,2\n",
                encoding="utf-8",
            )
            conn = sqlite3.connect(":memory:")
            ensure_sd_schema(conn)
            count = load_insurance_csv(path, conn, practice_id="")
            self.assertEqual(count, 2)
            cur = conn.cursor()
            cur.execute(
                "SELECT member_id, insurance_name, priority FROM sd_patient_insurance WHERE patient_id='P100'"
            )
            row = cur.fetchone()
            self.assertIsNone(row[0])  # empty PolicyNumber → NULL
            self.assertEqual(row[1], "Delta Dental")
            cur.execute(
                "SELECT member_id, priority FROM sd_patient_insurance WHERE patient_id='P200'"
            )
            row2 = cur.fetchone()
            self.assertEqual(row2[0], "MEM999")
            self.assertEqual(row2[1], 2)
            conn.close()

    def test_carrier_payer_map_lookup(self) -> None:
        from softdent_odbc_extract import lookup_carrier_payer_id, upsert_carrier_payer_map

        conn = sqlite3.connect(":memory:")
        ensure_sd_schema(conn)
        upsert_carrier_payer_map(
            conn, practice_id="", carrier_code="DELTA", payer_id="CX001", insurance_name="Delta"
        )
        self.assertEqual(lookup_carrier_payer_id(conn, practice_id="", carrier_code="DELTA"), "CX001")
        self.assertIsNone(lookup_carrier_payer_id(conn, practice_id="", carrier_code="UNKNOWN"))
        conn.close()

    def test_relationship_and_termination_helpers(self) -> None:
        from softdent_odbc_extract import _normalize_relationship_code, _termination_still_active

        self.assertEqual(_normalize_relationship_code("1"), "SELF")
        self.assertEqual(_normalize_relationship_code("spouse"), "SPOUSE")
        self.assertTrue(_termination_still_active(None, today="2026-07-11"))
        self.assertFalse(_termination_still_active("2026-01-01", today="2026-07-11"))
        self.assertTrue(_termination_still_active("2026-12-31", today="2026-07-11"))

    def test_extract_patient_insurance_mock_odbc(self) -> None:
        from softdent_odbc_extract import extract_patient_insurance

        class _Cur:
            description = [
                ("patient_id",),
                ("priority",),
                ("member_id",),
                ("insurance_name",),
                ("payer_id",),
                ("carrier_code",),
                ("relationship_code",),
                ("termination_date",),
            ]

            def execute(self, *_a, **_k):
                return None

            def fetchall(self):
                return [
                    ("P1", 1, "", "Delta Dental", None, "DELTA", "1", None),
                    ("P2", 1, "M2", "MetLife", "PAY2", "MET", "2", "2099-01-01"),
                ]

        class _Odbc:
            def cursor(self):
                return _Cur()

        conn = sqlite3.connect(":memory:")
        ensure_sd_schema(conn)
        n = extract_patient_insurance(_Odbc(), conn, practice_id="", sql="SELECT 1")
        self.assertEqual(n, 2)
        cur = conn.cursor()
        cur.execute("SELECT member_id, relationship_code FROM sd_patient_insurance WHERE patient_id='P1'")
        r1 = cur.fetchone()
        self.assertIsNone(r1[0])
        self.assertEqual(r1[1], "SELF")
        conn.close()


if __name__ == "__main__":
    unittest.main()
