"""SoftDent report-pull teaching playbook for HAL."""

from __future__ import annotations

import unittest

from softdent_report_pull import (
    format_softdent_report_pull_hal_reply,
    office_report_catalog,
    query_touches_softdent_report_pull,
    universal_report_pull_steps,
)


class SoftDentReportPullTests(unittest.TestCase):
    def test_universal_steps_and_catalog(self):
        steps = universal_report_pull_steps()
        self.assertGreaterEqual(len(steps), 7)
        self.assertTrue(any("Excel" in s for s in steps))
        self.assertTrue(any("Printer" in s for s in steps))
        cat = office_report_catalog()
        ids = {r["id"] for r in cat}
        self.assertIn("register", ids)
        self.assertIn("aging", ids)
        self.assertIn("daysheet", ids)

    def test_hal_reply_teaches_pull(self):
        text = format_softdent_report_pull_hal_reply("How do I pull SoftDent reports?")
        self.assertIn("HOW TO PULL SOFTDENT REPORTS", text)
        self.assertIn("Output Options", text)
        self.assertIn("Excel", text)
        self.assertIn("Print Preview", text)
        self.assertIn("NEVER Printer", text)
        self.assertIn("Registers", text)
        self.assertIn("SoftDentReportExports", text)
        self.assertTrue(
            "run_softdent_report_manager_multi_pull" in text
            or "run_softdent_money_widget_pull" in text
        )

    def test_query_touch_and_local_policy(self):
        self.assertTrue(query_touches_softdent_report_pull("How do I pull SoftDent reports?"))
        self.assertTrue(query_touches_softdent_report_pull("Teach HAL SoftDent report export"))
        self.assertTrue(query_touches_softdent_report_pull("how do I export SoftDent aging"))
        from nr2_hal_gateway import try_local_policy_reply

        hit = try_local_policy_reply("How do I pull SoftDent reports?")
        self.assertIsNotNone(hit)
        self.assertEqual(hit.get("intent"), "policy:softdent-report-pull")
        self.assertIn("Excel", hit.get("text") or "")

    def test_aging_specific(self):
        text = format_softdent_report_pull_hal_reply("pull SoftDent Account Aging to Excel")
        self.assertIn("Account Aging", text)
        self.assertIn("Accounting", text)


if __name__ == "__main__":
    unittest.main()
