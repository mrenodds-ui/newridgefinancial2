"""HAL SoftDent export consent E2E — consent gate + refreshImportsSuggested (empty ≠ $0)."""

from __future__ import annotations

import unittest
from unittest.mock import patch


class HalSoftdentExportConsentTests(unittest.TestCase):
    def test_consent_required(self) -> None:
        from hal_brain_tools import softdent_export

        out = softdent_export(consent=False, report_id="aging")
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("error"), "consent_required")

    def test_unreachable_when_softdent_not_running(self) -> None:
        from hal_brain_tools import softdent_export

        with patch("softdent_gui_export.softdent_main_running", return_value=False):
            out = softdent_export(consent=True, report_id="aging")
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("error"), "softdent_gui_unreachable")
        self.assertIn("SoftDentReportExports", out.get("pathHygiene") or "")

    def test_success_flags_import_refresh(self) -> None:
        from hal_brain_tools import softdent_export

        with (
            patch("softdent_gui_export.softdent_main_running", return_value=True),
            patch(
                "softdent_gui_export.export_report_by_id",
                return_value=r"C:\SoftDentReportExports\AG260715.XLS",
            ),
        ):
            out = softdent_export(consent=True, report_id="aging", days=30)
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("reportId"), "aging")
        self.assertTrue(out.get("refreshImportsSuggested"))
        self.assertIn("AG260715", out.get("path") or "")
        self.assertTrue(out.get("emptyNotZero"))

    def test_execute_action_softdent_export(self) -> None:
        from hal_brain_tools import execute_action, propose_action

        proposed = propose_action(
            kind="softdent_export",
            label="Export aging",
            payload={"reportId": "aging", "days": 30, "refreshImports": True},
        )
        action_id = proposed["action"]["actionId"]
        with patch(
            "hal_brain_tools.softdent_export",
            return_value={
                "ok": True,
                "path": r"C:\SoftDentReportExports\AG260715.XLS",
                "refreshImportsSuggested": True,
            },
        ) as mocked:
            out = execute_action(action_id=action_id, consent=True)
        self.assertTrue(out.get("ok"))
        mocked.assert_called_once()
        self.assertEqual(out["action"]["status"], "executed")
        self.assertTrue((out.get("result") or {}).get("refreshImportsSuggested"))


if __name__ == "__main__":
    unittest.main()
