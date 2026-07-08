"""Tests for nr2_analytics Tier-1 binders."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nr2_analytics import (
    analytics_snapshot,
    collection_lag,
    kpi_ribbon,
    production_reconciliation,
    quickbooks_monthly_revenue,
    softdent_production_daily,
)


def _sample_bundle() -> dict:
    return {
        "loadedAt": "2026-07-08T00:00:00+00:00",
        "softdent": {
            "dashboard": [
                {"period": "2026-05", "production": 100000, "collections": 92000},
                {"period": "2026-06", "production": 110000, "collections": 95000},
            ],
            "ar": {
                "rows": [
                    {"Bucket": "0-30", "Amount": 50000},
                    {"Bucket": "31-60", "Amount": 20000},
                    {"Bucket": "90+", "Amount": 10000},
                ]
            },
        },
        "quickbooks": {
            "profitAndLoss": {
                "rows": [
                    {"Period": "2026-05", "TotalIncome": 98000},
                    {"Period": "2026-06", "TotalIncome": 108000},
                ]
            }
        },
    }


class Nr2AnalyticsTests(unittest.TestCase):
    def test_production_reconciliation_variance(self) -> None:
        result = production_reconciliation(bundle=_sample_bundle())
        self.assertTrue(result["hasData"])
        latest = result["latest"]
        self.assertEqual(latest["period"], "2026-06")
        self.assertAlmostEqual(latest["variancePct"], -1.8, places=1)

    def test_collection_lag_dso(self) -> None:
        result = collection_lag(bundle=_sample_bundle())
        self.assertTrue(result["hasData"])
        self.assertTrue(result["dsoProxy"])
        self.assertGreater(result["avgLagDays"], 0)

    def test_quickbooks_monthly_revenue(self) -> None:
        result = quickbooks_monthly_revenue(bundle=_sample_bundle())
        self.assertTrue(result["hasData"])
        self.assertEqual(len(result["labels"]), 2)
        self.assertEqual(result["values"][-1], 108000)

    def test_kpi_ribbon_tiles(self) -> None:
        result = kpi_ribbon(bundle=_sample_bundle())
        self.assertTrue(result["hasData"])
        self.assertGreaterEqual(len(result["tiles"]), 2)

    def test_softdent_production_daily_monthly_fallback(self) -> None:
        with patch("nr2_analytics._sd_procedures_daily", return_value=[]), patch(
            "nr2_analytics._daysheet_daily_production", return_value=[]
        ):
            result = softdent_production_daily(bundle=_sample_bundle())
        self.assertTrue(result["hasData"])
        self.assertEqual(result["granularity"], "monthly")

    def test_analytics_snapshot_keys(self) -> None:
        snap = analytics_snapshot(bundle=_sample_bundle())
        for key in (
            "productionReconciliation",
            "collectionLag",
            "quickbooksMonthlyRevenue",
            "softdentProductionDaily",
            "kpiRibbon",
        ):
            self.assertIn(key, snap)


if __name__ == "__main__":
    unittest.main()
