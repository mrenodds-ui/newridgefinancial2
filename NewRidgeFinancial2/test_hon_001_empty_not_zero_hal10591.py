"""HAL-10591 / HON-001 — Empty ≠ $0 programmatic UI honesty enforcement."""

from __future__ import annotations

import unittest

from apex_backend import BUILD_ID, _money_kpi
from softdent_print_preview_audit import print_preview_audit_widget
from softdent_treatment_planning import build_tp_estimate_chip, _fmt_money
from ui_honesty_policy import (
    PACKAGE_BUILD_ID,
    SOURCE_GOLD_PAYMENT_LINES,
    SOURCE_PRINT_PREVIEW_VISUAL,
    audit_ui_honesty_surfaces,
    enforce_empty_not_zero,
    format_display_money,
    format_honesty_audit_reply,
    ui_honesty_widget,
)


class Hon001EmptyNotZeroHal10591Tests(unittest.TestCase):
    def test_build_id_coupled(self) -> None:
        self.assertEqual(PACKAGE_BUILD_ID, "hal-10591")
        self.assertEqual(BUILD_ID, "nr2-11000-clean")

    def test_null_never_renders_as_zero_dollars(self) -> None:
        for src in (SOURCE_GOLD_PAYMENT_LINES, SOURCE_PRINT_PREVIEW_VISUAL, "kpi"):
            with self.subTest(source=src):
                out = enforce_empty_not_zero(None, source_tag=src)
                self.assertEqual(out.get("display"), "—")
                self.assertNotEqual(out.get("display"), "$0.00")
                self.assertFalse(out.get("showDollars"))
                self.assertTrue(out.get("emptyIsNotZero"))

    def test_empty_string_never_renders_as_zero_dollars(self) -> None:
        out = enforce_empty_not_zero("", source_tag=SOURCE_GOLD_PAYMENT_LINES)
        self.assertEqual(out.get("display"), "—")
        self.assertIn("$0.00", format_display_money(0.0, source_tag="kpi"))  # explicit zero OK
        self.assertEqual(format_display_money(None, source_tag=SOURCE_GOLD_PAYMENT_LINES), "—")

    def test_explicit_zero_allowed(self) -> None:
        out = enforce_empty_not_zero(0.0, source_tag="kpi")
        self.assertEqual(out.get("display"), "$0.00")
        self.assertTrue(out.get("showDollars"))

    def test_visual_audit_badge_distinct_from_gold(self) -> None:
        visual = enforce_empty_not_zero(1.0, source_tag=SOURCE_PRINT_PREVIEW_VISUAL)
        gold = enforce_empty_not_zero(1.0, source_tag=SOURCE_GOLD_PAYMENT_LINES)
        self.assertEqual(visual.get("badge"), "visual")
        self.assertEqual(gold.get("badge"), "gold")
        self.assertNotEqual(visual.get("badge"), gold.get("badge"))
        self.assertIn("not a gold", str(visual.get("tooltip") or "").lower())

    def test_fmt_money_null_not_zero(self) -> None:
        self.assertNotEqual(_fmt_money(None), "$0.00")
        self.assertIn(_fmt_money(None), {"unknown", "—"})

    def test_tp_chip_insufficient_no_fake_zero(self) -> None:
        chip = build_tp_estimate_chip(
            {
                "ok": True,
                "found": False,
                "sufficient": False,
                "credibility": "insufficient",
                "sampleSize": 0,
                "source": SOURCE_GOLD_PAYMENT_LINES,
                "payer": "DELTA",
                "adaCode": "D1110",
            }
        )
        self.assertFalse(chip.get("showDollars"))
        self.assertTrue(chip.get("emptyIsNotZero"))
        self.assertNotIn("$0.00", str(chip.get("display") or ""))

    def test_tp_chip_null_paid_no_fake_zero(self) -> None:
        chip = build_tp_estimate_chip(
            {
                "ok": True,
                "found": True,
                "sufficient": True,
                "credibility": "high",
                "sampleSize": 25,
                "source": "ledger_episode_5yr",
                "payer": "DELTA",
                "adaCode": "D1110",
                "estimate": {
                    "credibility": "high",
                    "tier": "exact",
                    "sampleSize": 25,
                    "source": "ledger_episode_5yr",
                    "paidAmountAvg": None,
                    "writeOffAvg": None,
                    "adaCode": "D1110",
                    "insuranceCompany": "DELTA",
                },
            }
        )
        self.assertFalse(chip.get("showDollars"))
        self.assertNotIn("$0.00", str(chip.get("display") or ""))

    def test_apex_money_kpi_null(self) -> None:
        kpi = _money_kpi("t", "Test", None, hint="x")
        self.assertIsNone(kpi.get("value"))
        self.assertEqual(kpi.get("status"), "empty")
        self.assertEqual(kpi.get("display"), "—")
        self.assertTrue(kpi.get("emptyIsNotZero"))

    def test_print_preview_widget_honesty_markers(self) -> None:
        w = print_preview_audit_widget()
        self.assertTrue(w.get("emptyIsNotZero"))
        self.assertFalse(w.get("triggersGoldIngest"))
        if int(w.get("paymentLines") or 0) == 0:
            self.assertEqual(w.get("goldPaymentLinesDisplay"), "—")

    def test_audit_surfaces_pass(self) -> None:
        result = audit_ui_honesty_surfaces()
        self.assertTrue(result.get("ok"), result.get("findings"))
        self.assertEqual(result.get("failCount"), 0)
        text = format_honesty_audit_reply(result)
        self.assertIn("HAL-10591", text)
        self.assertIn("empty != $0", text)

    def test_honesty_widget(self) -> None:
        w = ui_honesty_widget()
        self.assertEqual(w.get("packageBuildId"), "hal-10591")
        self.assertTrue(w.get("emptyIsNotZero"))
        self.assertEqual(w.get("status"), "ok")


if __name__ == "__main__":
    unittest.main()
