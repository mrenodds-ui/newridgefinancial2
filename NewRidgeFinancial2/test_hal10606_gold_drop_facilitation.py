"""HAL-10606 — Gold CSV drop facilitation for settlement_matrix hydrate."""

from __future__ import annotations

import unittest

from apex_backend import BUILD_ID
from softdent_gold_drop_facilitation_hal10606 import (
    PACKAGE_BUILD_ID,
    format_hal10606_reply,
    gold_drop_facilitation_playbook,
    gold_drop_facilitation_widget,
    run_ops_10606_gold_drop_facilitation,
    staff_briefing,
    verify_export_path_writable,
)


class Hal10606GoldDropFacilitationTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(PACKAGE_BUILD_ID, "hal-10606")
        self.assertEqual(BUILD_ID, "hal-10608")

    def test_export_path_writable(self) -> None:
        out = verify_export_path_writable()
        self.assertTrue(out.get("ok"))
        self.assertTrue(out.get("writable"))

    def test_staff_briefing_honesty(self) -> None:
        b = staff_briefing()
        self.assertIn("Do not edit the CSV", " ".join(b.get("do") or []))
        self.assertTrue(any("Invent" in x or "invent" in x for x in (b.get("doNot") or [])))
        self.assertIn("v19", b.get("v19Reality") or "")

    def test_playbook_keeps_print_preview_honesty(self) -> None:
        p = gold_drop_facilitation_playbook()
        self.assertEqual(p.get("package"), "HAL-10606")
        self.assertFalse(p.get("excelAvailable"))
        self.assertEqual(p.get("outputMode"), "print_preview_only")

    def test_run_facilitation_no_invented_gold(self) -> None:
        result = run_ops_10606_gold_drop_facilitation(attempt_gui_export=False)
        self.assertTrue(result.get("ok"))
        self.assertFalse(result.get("inventedGold"))
        self.assertTrue(result.get("emptyIsNotZero"))
        acc = result.get("acceptance") or {}
        self.assertEqual(acc.get("gapCode"), "GOLD_CSV_MISSING")
        self.assertEqual(int(acc.get("paymentLines") or 0), 0)
        self.assertFalse(acc.get("acceptanceGateMet"))
        self.assertIn("GOLD_CSV_MISSING", str(acc.get("blockedReason") or ""))
        text = format_hal10606_reply(result)
        self.assertIn("HAL-10606", text)
        self.assertIn("empty != $0", text)

    def test_widget(self) -> None:
        w = gold_drop_facilitation_widget()
        self.assertEqual(w.get("def"), "HAL-10606")
        self.assertIn("gold-drop-facilitation", w.get("apiStatus") or "")


if __name__ == "__main__":
    unittest.main()
