"""SoftDent Report Manager multi-report programming tests."""

from __future__ import annotations

import unittest
from datetime import date
from unittest import mock

from softdent_report_manager_multi import (
    GROUP_NAME,
    MULTI_REPORT_PACK,
    format_report_manager_multi_hal_reply,
    report_manager_playbook,
    run_programmed_multi_report_pull,
)


class SoftDentReportManagerMultiTests(unittest.TestCase):
    def test_pack_covers_phase1_money_ids(self) -> None:
        ids = [r["id"] for r in MULTI_REPORT_PACK]
        for rid in ("register", "collections", "transactions", "daysheet", "aging"):
            self.assertIn(rid, ids)
        self.assertEqual(GROUP_NAME, "NR2 Money Widgets")
        play = report_manager_playbook()
        self.assertIn("Excel", " ".join(play["hardRules"]))
        self.assertTrue(all("Printer" not in str(r.get("output")) for r in MULTI_REPORT_PACK))

    def test_dry_run_sequential_fallback(self) -> None:
        with mock.patch(
            "softdent_report_manager_multi.probe_report_manager_menus",
            return_value={
                "ok": False,
                "reportManagerEnabled": True,
                "gapCode": "REPORT_MANAGER_RIGHTS_LOCKED",
                "items": {},
            },
        ):
            out = run_programmed_multi_report_pull(
                start=date(2026, 7, 1),
                end=date(2026, 7, 13),
                ensure_signon=False,
                dry_run=True,
            )
        self.assertEqual(out.get("mode"), "sequential_catalog_excel")
        self.assertTrue(out.get("ok"))
        self.assertIn("NR2 Money Widgets", format_report_manager_multi_hal_reply(out))


if __name__ == "__main__":
    unittest.main()
