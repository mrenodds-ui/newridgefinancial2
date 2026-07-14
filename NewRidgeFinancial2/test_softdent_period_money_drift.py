"""SoftDent Register vs daysheet_totals drift — unit tests (no SoftDent UI)."""

from __future__ import annotations

import unittest
from datetime import date
from unittest import mock

from softdent_period_money_drift import (
    compare_register_to_daysheet_totals,
    format_drift_hal_reply,
)


class SoftDentPeriodMoneyDriftTests(unittest.TestCase):
    def test_missing_register(self):
        with mock.patch("softdent_period_money_drift._find_register_xls", return_value=None):
            report = compare_register_to_daysheet_totals(
                start=date(2026, 7, 1),
                end=date(2026, 7, 12),
            )
        self.assertEqual(report.get("error"), "register_xls_missing")
        self.assertFalse(report.get("ok"))
        self.assertIn("Register", format_drift_hal_reply(report))

    def test_agree_within_tolerance(self):
        fake_path = mock.Mock()
        fake_path.__str__ = lambda self: r"C:\SoftDentReportExports\register.xls"
        with mock.patch(
            "softdent_period_money_drift._find_register_xls",
            return_value=fake_path,
        ):
            with mock.patch(
                "softdent_period_money_drift.parse_softdent_register_xls",
                return_value={
                    "production": 100.0,
                    "collections": 50.0,
                    "insPlanCollections": 0.0,
                    "regularCollections": 50.0,
                    "collectionsFormatRequired": True,
                },
            ):
                with mock.patch(
                    "softdent_period_money_drift._daysheet_totals_row",
                    return_value={
                        "gross_production": 100.0,
                        "net_production": 90.0,
                        "collections": 50.0,
                        "year_month": "2026-07",
                    },
                ):
                    report = compare_register_to_daysheet_totals(
                        start=date(2026, 7, 1),
                        end=date(2026, 7, 12),
                    )
        self.assertTrue(report.get("ok"))
        self.assertEqual(report.get("driftFields"), [])
        self.assertIn("agree", format_drift_hal_reply(report).lower())

    def test_detects_production_drift(self):
        fake_path = mock.Mock()
        with mock.patch(
            "softdent_period_money_drift._find_register_xls",
            return_value=fake_path,
        ):
            with mock.patch(
                "softdent_period_money_drift.parse_softdent_register_xls",
                return_value={
                    "production": 44735.0,
                    "collections": 29965.32,
                    "insPlanCollections": 0.0,
                    "regularCollections": 29965.32,
                    "collectionsFormatRequired": True,
                },
            ):
                with mock.patch(
                    "softdent_period_money_drift._daysheet_totals_row",
                    return_value={
                        "gross_production": 45684.25,
                        "collections": 29965.32,
                        "year_month": "2026-07",
                    },
                ):
                    report = compare_register_to_daysheet_totals(
                        start=date(2026, 7, 1),
                        end=date(2026, 7, 12),
                    )
        self.assertFalse(report.get("ok"))
        self.assertIn("production", report.get("driftFields") or [])


if __name__ == "__main__":
    unittest.main()
