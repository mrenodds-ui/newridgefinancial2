"""hal-10628 — HAL spine tiles resolve to live HAL widget ids."""

from __future__ import annotations

import unittest

from apex_backend import BUILD_ID, resolve_hal_board_actions


class Hal10625SpineWireTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10631")

    def test_import_health_focuses_hal_tile(self) -> None:
        out = resolve_hal_board_actions({"query": "focus import health", "page": "hal"})
        wids = [a.get("widgetId") for a in (out.get("actions") or []) if a.get("type") == "focus_widget"]
        self.assertIn("hal-import-health", wids)

    def test_program_posture_focuses_hal_tile(self) -> None:
        out = resolve_hal_board_actions({"query": "highlight program posture", "page": "hal"})
        wids = [a.get("widgetId") for a in (out.get("actions") or []) if a.get("type") == "focus_widget"]
        self.assertIn("hal-program-posture", wids)

    def test_ai_insight_focuses_hal_tile(self) -> None:
        out = resolve_hal_board_actions({"query": "show me the ai insight widget", "page": "hal"})
        wids = [a.get("widgetId") for a in (out.get("actions") or []) if a.get("type") == "focus_widget"]
        self.assertIn("hal-ai-insight", wids)


if __name__ == "__main__":
    unittest.main()
