"""Unit tests for HAL widget census skip + Collections pending helpers."""

from __future__ import annotations

import unittest

from apex_backend import (
    COLLECTIONS_PENDING_FIX,
    append_collections_pending_board_actions,
    census_has_collections_pending,
    format_census_reply,
    summarize_widget_census,
)


class HalCollectionsCensusTests(unittest.TestCase):
    def test_summarize_skips_hal_chat_by_type_not_only_id_prefix(self) -> None:
        census = summarize_widget_census(
            [
                {"id": "hal-ask", "type": "hal-chat", "label": "Ask HAL", "status": "ok"},
                {
                    "id": "hal-mosaic-prod",
                    "type": "kpi",
                    "label": "Production",
                    "value": 1000,
                    "status": "ok",
                },
                {
                    "id": "hal-mosaic-coll",
                    "type": "kpi",
                    "label": "Collections",
                    "value": None,
                    "status": "empty",
                    "hint": "Collections pending/missing — import SoftDent daysheet.",
                },
            ]
        )
        self.assertEqual(census["withData"], 1)
        self.assertEqual(census["empty"], 1)
        self.assertEqual(census["total"], 2)
        self.assertNotIn("hal-ask", census["populatedIds"])
        self.assertEqual(census["emptyIds"], ["hal-mosaic-coll"])

    def test_census_has_collections_pending(self) -> None:
        census = {
            "emptyWidgets": [
                {
                    "id": "hal-mosaic-coll",
                    "label": "Collections",
                    "hint": "Collections pending/missing — import SoftDent daysheet.",
                }
            ]
        }
        self.assertTrue(census_has_collections_pending(census))
        self.assertFalse(census_has_collections_pending({"emptyWidgets": []}))

    def test_format_census_reply_includes_collections_fix(self) -> None:
        census = {
            "withData": 7,
            "empty": 1,
            "total": 8,
            "emptyWidgets": [
                {
                    "id": "hal-mosaic-coll",
                    "label": "Collections",
                    "hint": "Collections pending/missing.",
                }
            ],
        }
        reply = format_census_reply("hal", census)
        self.assertIn("Collections", reply)
        self.assertIn(COLLECTIONS_PENDING_FIX[:40], reply)

    def test_append_collections_pending_board_actions(self) -> None:
        actions: list[dict] = []
        append_collections_pending_board_actions(actions)
        types = [a.get("type") for a in actions]
        self.assertIn("set_status_banner", types)
        self.assertIn("navigate", types)
        self.assertIn("focus_widget", types)
        nav = next(a for a in actions if a.get("type") == "navigate")
        self.assertEqual(nav.get("page"), "softdent")
        focus = next(a for a in actions if a.get("type") == "focus_widget")
        self.assertEqual(focus.get("widgetId"), "sd-collections")


if __name__ == "__main__":
    unittest.main()
