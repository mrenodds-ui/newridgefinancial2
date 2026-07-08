"""Tests for nr2_qb_reports (hal-10071)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from nr2_qb_reports import (
    ar_aging,
    balance_sheet_summary,
    cash_flow_trend,
    net_income_summary,
    revenue_by_service,
    sync_extended_qb_reports,
    write_report_cache,
)


def _sample_bundle() -> dict:
    return {
        "quickbooks": {
            "profitAndLoss": {
                "rows": [
                    {"Period": "2026-05", "TotalIncome": 98000, "TotalExpense": 70000, "NetIncome": 28000},
                    {"Period": "2026-06", "TotalIncome": 108000, "TotalExpense": 76000, "NetIncome": 32000},
                ]
            },
            "ar": {
                "rows": [
                    {"Bucket": "0-30", "Balance": 12500},
                    {"Bucket": "31-60", "Balance": 3200},
                ]
            },
        }
    }


class Nr2QbReportsTests(unittest.TestCase):
    def test_net_income_summary(self) -> None:
        result = net_income_summary(bundle=_sample_bundle())
        self.assertTrue(result["hasData"])
        self.assertEqual(result["ytdNetIncome"], 60000.0)

    def test_cash_flow_trend(self) -> None:
        result = cash_flow_trend(bundle=_sample_bundle())
        self.assertTrue(result["hasData"])
        self.assertEqual(len(result["labels"]), 2)

    def test_balance_sheet_summary(self) -> None:
        result = balance_sheet_summary(bundle=_sample_bundle())
        self.assertTrue(result["hasData"])
        self.assertGreater(len(result["assets"]), 0)

    def test_ar_aging_from_import(self) -> None:
        result = ar_aging(bundle=_sample_bundle())
        self.assertTrue(result["hasData"])
        self.assertEqual(result["total"], 15700.0)

    def test_sync_extended_reports_writes_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            with mock.patch("nr2_qb_reports.quickbooks_import_dir", return_value=dest):
                result = sync_extended_qb_reports(bundle=_sample_bundle())
            self.assertTrue(result["ok"])
            cache_path = dest / "qb_report_cache.json"
            self.assertTrue(cache_path.is_file())
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertIn("reports", payload)


if __name__ == "__main__":
    unittest.main()
