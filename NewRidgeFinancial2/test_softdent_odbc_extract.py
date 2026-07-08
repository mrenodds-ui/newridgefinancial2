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
                ["", "1002", "John Smith", "", "DR1", "1200", "Visa Card Payment", "85.00", "", "", "", "", "", "", ""],
            ]
        },
    }
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


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
            claims.write_text(
                "ClaimId,PatientName,Payer,ServiceDate,ClaimAmount,ClaimStatus\n"
                "CLM-001,Jane Doe,Delta Dental,2026-06-10,420.00,Ready\n",
                encoding="utf-8",
            )
            with patch("softdent_odbc_extract.resolve_sd_sqlite_db", return_value=db_path), patch(
                "softdent_odbc_extract._resolve_daysheet_path", return_value=daysheet
            ), patch("softdent_odbc_extract._resolve_claims_path", return_value=claims):
                result = extract_softdent_odbc(force=True)
            self.assertTrue(result["ok"])
            self.assertEqual(result["mode"], "json-fallback")
            counts = table_row_counts(db_path)
            self.assertGreater(counts["sd_procedures"], 0)
            self.assertGreater(counts["sd_patients"], 0)
            self.assertGreater(counts["sd_claims"], 0)
            self.assertGreaterEqual(result["tableCounts"]["sd_payments"], 1)

    def test_odbc_lane_graceful_without_dsn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analytics.sqlite3"
            conn = sqlite3.connect(db_path)
            ensure_sd_schema(conn)
            conn.close()
            with patch("softdent_odbc_extract.resolve_sd_sqlite_db", return_value=db_path), patch(
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
            with patch("softdent_odbc_extract.resolve_sd_sqlite_db", return_value=db_path), patch(
                "softdent_odbc_extract._resolve_daysheet_path", return_value=daysheet
            ), patch("softdent_odbc_extract._resolve_claims_path", return_value=Path("")):
                extract_softdent_odbc(force=True)
            status = read_extract_status(db_path)
            self.assertEqual(status["lastMode"], "json-fallback")
            self.assertGreaterEqual(int(status["populatedTables"] or 0), 3)


if __name__ == "__main__":
    unittest.main()
