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


if __name__ == "__main__":
    unittest.main()
