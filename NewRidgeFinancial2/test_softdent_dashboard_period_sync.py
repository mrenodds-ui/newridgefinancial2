"""Tests for SoftDent dashboard period sync collections handling."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from softdent_dashboard_period_sync import _build_period_row, diagnose_collections_gap


class SoftdentDashboardPeriodSyncTests(unittest.TestCase):
    def test_provider_production_does_not_force_zero_collections(self) -> None:
        row = _build_period_row(
            "2026-06",
            [
                {"_source": "provider_prod", "production": 169318.9},
                {"_source": "bridge", "production": 168790.0, "collections": 0.0, "insurance": 0.0, "patient": 0.0},
            ],
        )
        self.assertEqual(row["production"], 169318.9)
        self.assertFalse(row.get("collectionsReported", True))
        self.assertNotIn("collectionsPending", row)

    def test_provider_only_marks_collections_pending(self) -> None:
        row = _build_period_row("2026-06", [{"_source": "provider_prod", "production": 169318.9}])
        self.assertTrue(row.get("collectionsPending"))
        self.assertNotIn("collectionsReported", row)

    def test_daysheet_collections_are_preserved(self) -> None:
        row = _build_period_row(
            "2026-05",
            [
                {"_source": "daysheet", "production": 128475.0, "collections": 71414.88, "insurance": 100.0, "patient": 71314.88},
                {"_source": "provider_prod", "production": 130295.6},
            ],
        )
        self.assertEqual(row["collections"], 71414.88)
        self.assertNotIn("collectionsReported", row)

    def test_diagnose_collections_gap_reports_zero_daysheet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analytics.sqlite3"
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE daysheet_totals (
                    year_month TEXT,
                    gross_production REAL,
                    net_production REAL,
                    collections REAL,
                    insurance_payment_total REAL
                )
                """
            )
            conn.execute(
                "INSERT INTO daysheet_totals VALUES ('2026-06', 120000, 120000, 0, 0)"
            )
            conn.commit()
            conn.close()
            diagnostic = diagnose_collections_gap(db_path, ["2026-06"])
            self.assertTrue(any("zero" in issue.lower() for issue in diagnostic["issues"]))


if __name__ == "__main__":
    unittest.main()
