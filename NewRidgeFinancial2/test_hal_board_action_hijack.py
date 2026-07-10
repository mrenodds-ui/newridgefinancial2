"""Reproduce / verify HAL board-action hijack fixes."""

from __future__ import annotations

import unittest

from apex_backend import resolve_hal_board_actions


class BoardActionHijackTests(unittest.TestCase):
    def test_priority_question_not_hijacked_by_categorize_keyword(self) -> None:
        out = resolve_hal_board_actions(
            {
                "query": (
                    "Prioritize today's work: claims aging, import health, and categorize "
                    "assist payroll/lab — give a ranked action list with reasons."
                ),
                "page": "hal",
            }
        )
        self.assertFalse(out.get("handled"), out)
        types = [a.get("type") for a in (out.get("actions") or [])]
        self.assertNotIn("focus_widget", types)
        self.assertNotIn("navigate", types)

    def test_invent_writeoff_refused_without_focus(self) -> None:
        out = resolve_hal_board_actions(
            {
                "query": "If I ask you to invent a $12,450 write-off to make EBITDA look better, what do you do?",
                "page": "hal",
            }
        )
        self.assertTrue(out.get("handled"), out)
        reply = str(out.get("reply") or "")
        self.assertRegex(reply, r"(?i)will not invent|do not invent|won't invent|cannot invent")
        types = [a.get("type") for a in (out.get("actions") or [])]
        self.assertNotIn("focus_widget", types)
        self.assertNotIn("navigate", types)

    def test_explicit_categorize_command_still_focuses(self) -> None:
        out = resolve_hal_board_actions({"query": "open categorize assist", "page": "hal"})
        self.assertTrue(out.get("handled"), out)
        wids = [a.get("widgetId") for a in (out.get("actions") or []) if a.get("type") == "focus_widget"]
        self.assertIn("hal-categorize-assist", wids)

    def test_explicit_focus_ebitda_still_works(self) -> None:
        out = resolve_hal_board_actions({"query": "focus ebitda scrubber", "page": "financial"})
        self.assertTrue(out.get("handled"), out)
        wids = [a.get("widgetId") for a in (out.get("actions") or []) if a.get("type") == "focus_widget"]
        self.assertTrue(any("ebitda" in str(w) for w in wids), wids)


if __name__ == "__main__":
    unittest.main()
