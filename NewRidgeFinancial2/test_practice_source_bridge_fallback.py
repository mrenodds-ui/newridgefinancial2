"""Tests for SoftDent dashboard bridge fallback validation."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from practice_source_access import _dashboard_from_bridge_fallback, _validate_bridge_dashboard_rows


class PracticeSourceBridgeFallbackTests(unittest.TestCase):
    def test_validate_bridge_dashboard_rows_flags_missing_period(self) -> None:
        validation = _validate_bridge_dashboard_rows([{"production": 1000.0}])
        self.assertFalse(validation["ok"])
        self.assertTrue(any("period" in issue for issue in validation["issues"]))

    def test_dashboard_from_bridge_fallback_marks_read_source(self) -> None:
        bridge_raw = {
            "ok": True,
            "derivedDashboardRows": [
                {
                    "provider": "Practice Total",
                    "period": "2026-06",
                    "production": 120000.0,
                    "collections": 0.0,
                    "insurance": 0.0,
                    "patient": 0.0,
                    "collectionsReported": False,
                }
            ],
            "sourceFile": "softdent_bridge_latest.json",
            "modifiedAt": "2026-07-01T12:00:00+00:00",
        }
        with patch("practice_source_access._fetch_softdent", return_value=bridge_raw):
            dataset = _dashboard_from_bridge_fallback()
        self.assertIsNotNone(dataset)
        assert dataset is not None
        self.assertEqual(dataset.get("readSource"), "bridge-fallback")
        self.assertTrue(dataset.get("bridgeValidation"))
        self.assertEqual(len(dataset.get("rows") or []), 1)


if __name__ == "__main__":
    unittest.main()
