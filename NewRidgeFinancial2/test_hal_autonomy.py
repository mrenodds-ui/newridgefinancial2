"""HAL read autonomy — QB sync / navigate consent-free; HAL shift does not block morning tick."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class HalAutonomyTests(unittest.TestCase):
    def test_hal_shift_does_not_block_morning_auto(self) -> None:
        from nr2_scheduler import _human_operator_shift_blocks_auto

        store = MagicMock()
        with patch(
            "employee_actions.get_current_shift_context",
            return_value={"active": True, "employeeId": "HAL", "tier": 7},
        ):
            self.assertFalse(_human_operator_shift_blocks_auto(store))

    def test_human_shift_blocks_morning_auto(self) -> None:
        from nr2_scheduler import _human_operator_shift_blocks_auto

        store = MagicMock()
        with patch(
            "employee_actions.get_current_shift_context",
            return_value={"active": True, "employeeId": "OM-Jane", "tier": 3},
        ):
            self.assertTrue(_human_operator_shift_blocks_auto(store))

    def test_qb_sync_runs_without_consent_flag(self) -> None:
        from hal_brain_tools import qb_sync

        with patch("qb_connector.sync_read_only", return_value={"ok": True, "rows": 1}):
            out = qb_sync(consent=False, store=MagicMock(), actor="test")
        self.assertTrue(out.get("ok"))
        self.assertFalse(out.get("consentRequired"))
        self.assertTrue(out.get("autonomous"))

    def test_is_read_autonomous_kinds(self) -> None:
        from hal_brain_tools import is_read_autonomous_kind

        self.assertTrue(is_read_autonomous_kind("qb_sync"))
        self.assertTrue(is_read_autonomous_kind("navigate"))
        self.assertTrue(is_read_autonomous_kind("softdent-export"))
        self.assertFalse(is_read_autonomous_kind("softdent_writeback"))
        self.assertFalse(is_read_autonomous_kind("email"))


if __name__ == "__main__":
    unittest.main()
