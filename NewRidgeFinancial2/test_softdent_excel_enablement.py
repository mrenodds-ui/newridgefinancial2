"""SoftDent Excel enablement runbook + morning-bundle gate tests."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class SoftDentExcelEnablementTests(unittest.TestCase):
    def test_runbook_exists(self) -> None:
        path = ROOT / "docs" / "runbooks" / "softdent_excel_enablement_nr2.md"
        self.assertTrue(path.is_file(), f"missing {path}")
        text = path.read_text(encoding="utf-8")
        self.assertIn("never File", text)
        self.assertIn("SoftDentReportExports", text)
        self.assertIn("empty", text.lower())

    def test_qb_inbox_runbook_exists(self) -> None:
        path = ROOT / "docs" / "runbooks" / "qb_ap_payroll_inbox_drop_nr2.md"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("quickbooks_ap_aging.csv", text)
        self.assertIn("empty", text.lower())
        self.assertIn("forceCloseAvailable", text)

    def test_hal_teach_points_at_runbook(self) -> None:
        from softdent_report_pull import format_softdent_report_pull_hal_reply, universal_report_pull_steps

        steps = " ".join(universal_report_pull_steps())
        self.assertIn("softdent_excel_enablement_nr2.md", steps)
        reply = format_softdent_report_pull_hal_reply("how do I pull SoftDent aging")
        self.assertIn("softdent_excel_enablement_nr2.md", reply)
        self.assertIn("never File", reply)

    def test_morning_bundle_exposes_excel_gate_constant(self) -> None:
        from hal_brain_tools import SOFTDENT_EXCEL_ENABLEMENT_RUNBOOK

        self.assertTrue(SOFTDENT_EXCEL_ENABLEMENT_RUNBOOK.endswith("softdent_excel_enablement_nr2.md"))


if __name__ == "__main__":
    unittest.main()
