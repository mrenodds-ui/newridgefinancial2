"""Integration honesty gate — widget null→$0 regression (HAL-10603).

Moonshot path: tests/integration/test_widget_regression.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

NR2 = Path(__file__).resolve().parents[2] / "NewRidgeFinancial2"
if str(NR2) not in sys.path:
    sys.path.insert(0, str(NR2))

from apex_backend import _money_kpi  # noqa: E402
from softdent_print_preview_audit import print_preview_audit_widget  # noqa: E402
from softdent_treatment_planning import build_tp_estimate_chip  # noqa: E402
from test_hal10603_honesty_ci import assert_no_fake_zero_dollars  # noqa: E402
from ui_honesty_policy import (  # noqa: E402
    SOURCE_GOLD_PAYMENT_LINES,
    enforce_empty_not_zero,
    format_display_money,
    ui_honesty_widget,
)


class WidgetHonestyRegressionTests(unittest.TestCase):
    def test_widget_json_null_not_string_zero(self) -> None:
        out = enforce_empty_not_zero(None, source_tag=SOURCE_GOLD_PAYMENT_LINES)
        self.assertNotEqual(out.get("display"), "$0.00")
        self.assertNotEqual(out.get("display"), "0.00")
        self.assertFalse(out.get("showDollars"))

    def test_show_dollars_false_hides_zero(self) -> None:
        chip = build_tp_estimate_chip(
            {
                "ok": True,
                "found": True,
                "sufficient": False,
                "credibility": "insufficient",
                "sampleSize": 0,
                "source": "carrier_alias_pending",
                "payer": "X",
                "adaCode": "D1110",
                "estimate": {"paidAmountAvg": None, "credibility": "insufficient"},
            }
        )
        assert_no_fake_zero_dollars(chip, ctx="widget_regression")
        self.assertFalse(chip.get("showDollars"))
        self.assertNotIn("$0.00", str(chip.get("display") or ""))

    def test_kpi_and_honesty_widgets(self) -> None:
        kpi = _money_kpi("collections", "Collections", None, hint="hint")
        self.assertNotEqual(kpi.get("value"), "$0.00")
        self.assertTrue(kpi.get("emptyIsNotZero"))
        self.assertTrue(ui_honesty_widget().get("emptyIsNotZero"))
        self.assertTrue(print_preview_audit_widget().get("emptyIsNotZero"))

    def test_format_display_money_dash_not_zero(self) -> None:
        self.assertEqual(format_display_money(None, source_tag=SOURCE_GOLD_PAYMENT_LINES), "—")


if __name__ == "__main__":
    unittest.main()
