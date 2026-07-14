"""Tests for SoftDent dashboard period sync collections handling."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from softdent_dashboard_period_sync import _build_period_row, _prior_source_dict, diagnose_collections_gap, sync_dashboard_period_rows


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

    def test_current_month_bridge_without_daysheet_marks_collections_pending(self) -> None:
        with patch("softdent_dashboard_period_sync._is_current_month", return_value=True):
            row = _build_period_row(
                "2026-07",
                [
                    {"_source": "provider_prod", "production": 10476.0},
                    {"_source": "bridge", "production": 10476.0, "collections": 0.0, "insurance": 0.0, "patient": 0.0},
                ],
            )
        self.assertTrue(row.get("collectionsPending"))
        self.assertNotIn("collectionsReported", row)
        self.assertNotIn("collections", row)

    def test_daysheet_collections_are_preserved(self) -> None:
        row = _build_period_row(
            "2026-05",
            [
                {"_source": "daysheet", "production": 128475.0, "collections": 71414.88, "insurance": 100.0, "patient": 71314.88},
                {"_source": "provider_prod", "production": 130295.6},
            ],
        )
        self.assertEqual(row["collections"], 71414.88)
        self.assertTrue(row.get("collectionsReported"))

    def test_daysheet_zero_collections_with_production_not_reported(self) -> None:
        row = _build_period_row(
            "2026-06",
            [
                {
                    "_source": "daysheet",
                    "production": 120000.0,
                    "collections": 0.0,
                    "insurance": 0.0,
                    "patient": 0.0,
                },
            ],
        )
        self.assertEqual(row["production"], 120000.0)
        self.assertFalse(row.get("collectionsReported", True))
        self.assertNotIn("collectionsPending", row)

    def test_prior_collections_preserved_when_provider_pending(self) -> None:
        prior = {
            "period": "2026-06",
            "production": 169318.9,
            "collections": 71414.88,
            "insurance": 0.0,
            "patient": 71414.88,
        }
        row = _build_period_row(
            "2026-06",
            [
                _prior_source_dict(prior),
                {"_source": "provider_prod", "production": 169318.9},
            ],
        )
        self.assertEqual(row.get("collections"), 71414.88)
        self.assertTrue(row.get("collectionsReported"))
        self.assertNotIn("collectionsPending", row)
        # Honesty: all-patient dump (ins=0, patient=collections) is not a real mix
        self.assertEqual(row.get("patient"), 0.0)
        self.assertEqual(row.get("insurance"), 0.0)
        self.assertTrue(row.get("collectionsFormatRequired"))

    def test_daysheet_without_insurance_split_marks_format_required(self) -> None:
        row = _build_period_row(
            "2026-05",
            [
                {
                    "_source": "daysheet",
                    "production": 128475.0,
                    "collections": 71414.88,
                    "insurance": 0.0,
                    "patient": 0.0,
                    "insuranceSplitReported": False,
                },
            ],
        )
        self.assertEqual(row.get("collections"), 71414.88)
        self.assertTrue(row.get("collectionsReported"))
        self.assertEqual(row.get("patient"), 0.0)
        self.assertTrue(row.get("collectionsFormatRequired"))

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

    def test_sync_dashboard_period_rows_records_merge_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            existing_path = dest / "softdent_dashboard_data.json"
            existing_path.write_text(
                json.dumps(
                    [
                        {
                            "period": "2026-06",
                            "production": 100.0,
                            "collections": 50.0,
                            "provider": "Test",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            with patch("softdent_dashboard_period_sync.softdent_import_dir", return_value=dest):
                with patch("softdent_dashboard_period_sync.relevant_period_labels", return_value=["2026-06"]):
                    with patch("softdent_dashboard_period_sync.resolve_analytics_db", return_value=None):
                        with patch(
                            "softdent_dashboard_period_sync._month_rows",
                            return_value=[
                                {
                                    "period": "2026-06",
                                    "production": 120.0,
                                    "collectionsPending": True,
                                    "provider": "New Ridge Family Dental",
                                }
                            ],
                        ):
                            result = sync_dashboard_period_rows()
            self.assertTrue(result.get("ok"))
            merge_log = result.get("mergeLog") or []
            self.assertTrue(any(entry.get("action") == "upsert" for entry in merge_log))
            upsert = next(entry for entry in merge_log if entry.get("action") == "upsert")
            self.assertEqual(upsert.get("priorCollections"), 50.0)
            self.assertEqual(upsert.get("mergedCollections"), 50.0)


if __name__ == "__main__":
    unittest.main()
