"""Tests for nr2_analytics Tier-1 binders."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nr2_analytics import (
    alert_ticker,
    analytics_snapshot,
    collection_deposit_variance,
    collection_lag,
    goal_scorecard,
    kpi_ribbon,
    monthly_trend_combo,
    production_reconciliation,
    provider_compensation,
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

    def test_collection_lag_prior_period_when_open_month_pending(self) -> None:
        bundle = {
            "softdent": {
                "dashboard": [
                    {"period": "2026-05", "production": 100000, "collections": 92000},
                    {"period": "2026-06", "production": 110000, "collections": 95000},
                    {
                        "period": "2026-07",
                        "production": 40000,
                        "collections": 0,
                        "collectionsPending": True,
                    },
                ],
                "ar": {"rows": []},
            }
        }
        result = collection_lag(bundle=bundle)
        self.assertTrue(result["hasData"])
        self.assertFalse(result["dsoProxy"])
        self.assertTrue(result["priorPeriodProxy"])
        self.assertEqual(result["period"], "2026-06")
        # 30 * (1 - 95000/110000) = 4.1
        self.assertAlmostEqual(result["avgLagDays"], 4.1, places=1)
        self.assertIn("2026-06", result["caption"])
        self.assertIn("2026-07", result["caption"])

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

    def test_collection_deposit_variance(self) -> None:
        bundle = _sample_bundle()
        with patch("nr2_analytics._qb_deposits_for_period", return_value=(94000.0, "test.probe")):
            result = collection_deposit_variance(bundle=bundle)
        self.assertTrue(result["hasData"])
        self.assertEqual(result["period"], "2026-06")
        self.assertAlmostEqual(result["variancePct"], -1.1, places=1)

    def test_analytics_snapshot_keys(self) -> None:
        snap = analytics_snapshot(bundle=_sample_bundle())
        for key in (
            "productionReconciliation",
            "collectionLag",
            "quickbooksMonthlyRevenue",
            "softdentProductionDaily",
            "kpiRibbon",
            "collectionDepositVariance",
            "goalScorecard",
            "alertTicker",
            "providerCompensation",
            "monthlyTrendCombo",
        ):
            self.assertIn(key, snap)

    def test_goal_scorecard(self) -> None:
        result = goal_scorecard(bundle=_sample_bundle())
        self.assertTrue(result["hasData"])
        self.assertGreater(result["ytdProduction"], 0)
        # Without NR2_GOAL_PRODUCTION_YTD, do not invent a synthetic target/%.
        self.assertIsNone(result["pctOfGoal"])
        self.assertIsNone(result["targetProduction"])
        self.assertTrue(result.get("needsGoal"))

    def test_goal_scorecard_with_env_target(self) -> None:
        import os

        prev = os.environ.get("NR2_GOAL_PRODUCTION_YTD")
        os.environ["NR2_GOAL_PRODUCTION_YTD"] = "1000000"
        try:
            result = goal_scorecard(bundle=_sample_bundle())
            self.assertTrue(result["hasData"])
            self.assertIsNotNone(result["pctOfGoal"])
            self.assertEqual(result["targetProduction"], 1000000.0)
            self.assertFalse(result.get("needsGoal"))
        finally:
            if prev is None:
                os.environ.pop("NR2_GOAL_PRODUCTION_YTD", None)
            else:
                os.environ["NR2_GOAL_PRODUCTION_YTD"] = prev

    def test_alert_ticker(self) -> None:
        result = alert_ticker(bundle=_sample_bundle())
        self.assertIn("items", result)
        self.assertIn("hasData", result)
        # Never invent a green "all clear" filler when no thresholds fire.
        self.assertTrue(all("within normal review" not in str(item.get("text") or "").lower() for item in result["items"]))
        if result["items"]:
            self.assertTrue(result["hasData"])
        else:
            self.assertFalse(result["hasData"])

    def test_provider_compensation(self) -> None:
        result = provider_compensation(bundle=_sample_bundle())
        self.assertIn("providers", result)
        self.assertIn("hasData", result)

    def test_monthly_trend_combo(self) -> None:
        result = monthly_trend_combo(bundle=_sample_bundle())
        self.assertTrue(result["hasData"])
        self.assertEqual(len(result["labels"]), len(result["production"]))


if __name__ == "__main__":
    unittest.main()
