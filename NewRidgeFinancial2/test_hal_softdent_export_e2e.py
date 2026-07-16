"""HAL SoftDent export E2E — consent-free GUI Excel export + refreshImportsSuggested (empty ≠ $0)."""

from __future__ import annotations

import unittest
from unittest.mock import patch


class HalSoftdentExportConsentTests(unittest.TestCase):
    def test_session_doctrine_teaches_export_consent_free(self) -> None:
        from hal_session_store import HAL_9000_BRAIN_SYSTEM

        doctrine = HAL_9000_BRAIN_SYSTEM
        self.assertIn("consent-free", doctrine.lower())
        self.assertIn("SoftDent Excel/Print Preview GUI export", doctrine)
        self.assertIn("QB read-only sync", doctrine)
        self.assertNotIn("Outbound and GUI exports require explicit operator consent.", doctrine)
        self.assertIn("write-back", doctrine.lower())
        self.assertNotIn("QB sync (requires consent)", doctrine)

    def test_propose_softdent_export_marks_consent_not_required(self) -> None:
        from hal_brain_tools import propose_action

        out = propose_action(kind="softdent_export", label="Aging Excel")
        self.assertTrue(out.get("ok"))
        self.assertFalse(out.get("consentRequired"))
        self.assertFalse((out.get("action") or {}).get("consentRequired"))

    def test_propose_qb_sync_is_consent_free(self) -> None:
        from hal_brain_tools import propose_action

        out = propose_action(kind="qb_sync", label="QB sync")
        self.assertTrue(out.get("ok"))
        self.assertFalse(out.get("consentRequired"))
        self.assertTrue((out.get("action") or {}).get("autonomous"))

    def test_propose_navigate_is_consent_free(self) -> None:
        from hal_brain_tools import propose_action

        out = propose_action(kind="navigate", label="Open SoftDent", payload={"page": "softdent"})
        self.assertTrue(out.get("ok"))
        self.assertFalse(out.get("consentRequired"))

    def test_execute_qb_sync_without_consent(self) -> None:
        from hal_brain_tools import execute_action, propose_action

        proposed = propose_action(kind="qb_sync", label="QB sync", payload={"refreshImports": True})
        action_id = proposed["action"]["actionId"]
        with patch(
            "hal_brain_tools.qb_sync",
            return_value={"ok": True, "autonomous": True, "consentRequired": False},
        ) as mocked:
            out = execute_action(action_id=action_id, consent=False, store=None)
        self.assertTrue(out.get("ok"))
        mocked.assert_called_once()
        self.assertEqual(out["action"]["status"], "executed")

    def test_export_runs_without_consent_flag(self) -> None:
        from hal_brain_tools import softdent_export

        with patch("softdent_gui_export.softdent_main_running", return_value=False):
            out = softdent_export(consent=False, report_id="aging")
        # consent ignored — failure is SoftDent unreachable, not consent_required
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("error"), "softdent_gui_unreachable")
        self.assertNotEqual(out.get("error"), "consent_required")

    def test_unreachable_when_softdent_not_running(self) -> None:
        from hal_brain_tools import softdent_export

        with patch("softdent_gui_export.softdent_main_running", return_value=False):
            out = softdent_export(report_id="aging")
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
            out = softdent_export(report_id="aging", days=30)
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("reportId"), "aging")
        self.assertTrue(out.get("refreshImportsSuggested"))
        self.assertFalse(out.get("consentRequired"))
        self.assertIn("AG260715", out.get("path") or "")
        self.assertTrue(out.get("emptyNotZero"))

    def test_execute_action_softdent_export_without_consent(self) -> None:
        from hal_brain_tools import execute_action, propose_action

        proposed = propose_action(
            kind="softdent_export",
            label="Export aging",
            payload={"reportId": "aging", "days": 30, "refreshImports": True},
        )
        self.assertFalse(proposed.get("consentRequired"))
        action_id = proposed["action"]["actionId"]
        with patch(
            "hal_brain_tools.softdent_export",
            return_value={
                "ok": True,
                "path": r"C:\SoftDentReportExports\AG260715.XLS",
                "refreshImportsSuggested": True,
            },
        ) as mocked:
            out = execute_action(action_id=action_id, consent=False)
        self.assertTrue(out.get("ok"))
        mocked.assert_called_once()
        self.assertEqual(out["action"]["status"], "executed")
        self.assertTrue((out.get("result") or {}).get("refreshImportsSuggested"))


if __name__ == "__main__":
    unittest.main()
