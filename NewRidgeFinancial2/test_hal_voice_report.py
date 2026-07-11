"""Tests for Moonshot HAL voice + report programming (Phases 1–2)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from apex_backend import parse_voice_report_command, resolve_hal_board_actions


class VoiceReportParserTests(unittest.TestCase):
    def test_handoff_intent(self) -> None:
        hit = parse_voice_report_command("HAL, handoff report")
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit["tool"], "clock_out_shift")
        self.assertTrue(hit["speak"])
        self.assertEqual(hit["intent"], "handoff")

    def test_readiness_intent(self) -> None:
        hit = parse_voice_report_command("run readiness check")
        self.assertEqual((hit or {}).get("tool"), "readiness_diagnostics")

    def test_briefing_intent(self) -> None:
        hit = parse_voice_report_command("morning briefing")
        self.assertEqual((hit or {}).get("tool"), "daily_ops_briefing")

    def test_avoids_ebitda_collision(self) -> None:
        self.assertIsNone(parse_voice_report_command("set ebitda scrubber salary to 100"))

    def test_board_actions_emits_run_tool(self) -> None:
        with patch.dict(os.environ, {"NR2_VOICE_REPORTS": "1"}, clear=False):
            result = resolve_hal_board_actions({"query": "handoff report", "page": "hal"})
        self.assertTrue(result.get("handled"))
        types = [a.get("type") for a in (result.get("actions") or [])]
        self.assertIn("run_tool", types)
        tool_actions = [a for a in (result.get("actions") or []) if a.get("type") == "run_tool"]
        self.assertEqual(tool_actions[0].get("tool"), "clock_out_shift")

    def test_board_actions_disabled_by_env(self) -> None:
        with patch.dict(os.environ, {"NR2_VOICE_REPORTS": "0"}, clear=False):
            result = resolve_hal_board_actions({"query": "handoff report", "page": "hal"})
        types = [a.get("type") for a in (result.get("actions") or [])]
        self.assertNotIn("run_tool", types)


if __name__ == "__main__":
    unittest.main()
