"""Phase I2 validation — SoftDent Collections/Daysheet honesty (DEF-001)."""

from __future__ import annotations

import unittest

from apex_backend import build_apex_widgets, resolve_hal_board_actions
from apex_financial_console_pack import build_revenue_composition
from apex_program_improve_pack import assess_import_health
from apex_softdent_hardening_pack import (
    GAP_COLLECTIONS_PENDING,
    GAP_OK,
    GAP_REGISTER_ONLY,
    assess_collections_gap,
    collections_gap_widget,
    format_collections_gap_reply,
    import_health_collections_alert,
)


def _bundle_pending() -> dict:
    return {
        "softdent": {
            "dashboard": {
                "rows": [
                    {
                        "period": "2026-07",
                        "production": 50000,
                        "collectionsPending": True,
                        "insurance": 0,
                        "patient": 0,
                    }
                ]
            }
        },
        "diagnostics": {"summary": {"connected": 3, "total": 5, "missing": 2}},
        "loadedAt": "2026-07-11T12:00:00Z",
    }


def _bundle_ok() -> dict:
    return {
        "softdent": {
            "dashboard": {
                "rows": [
                    {
                        "period": "2026-07",
                        "production": 50000,
                        "collections": 42000,
                        "collectionsReported": True,
                        "insurance": 30000,
                        "patient": 12000,
                    }
                ]
            }
        },
        "diagnostics": {"summary": {"connected": 5, "total": 5, "missing": 0}},
        "loadedAt": "2026-07-11T12:00:00Z",
    }


def _bundle_register_only() -> dict:
    return {
        "softdent": {
            "dashboard": {
                "rows": [
                    {
                        "period": "2026-06",
                        "production": 40000,
                        # no collections key, not pending flag → REGISTER_ONLY
                    }
                ]
            }
        }
    }


class SoftDentHardeningPhaseI2Tests(unittest.TestCase):
    def test_pending_gap_code(self):
        gap = assess_collections_gap(_bundle_pending())
        self.assertEqual(gap.get("gapCode"), GAP_COLLECTIONS_PENDING)
        self.assertFalse(gap.get("healthy"))
        self.assertIsNone(gap.get("collections"))  # honesty: no invented $
        self.assertIn("daysheet", (gap.get("fixHint") or "").lower())

    def test_ok_gap_code(self):
        gap = assess_collections_gap(_bundle_ok())
        self.assertEqual(gap.get("gapCode"), GAP_OK)
        self.assertTrue(gap.get("healthy"))
        self.assertEqual(gap.get("collections"), 42000)

    def test_register_only(self):
        gap = assess_collections_gap(_bundle_register_only())
        self.assertEqual(gap.get("gapCode"), GAP_REGISTER_ONLY)
        self.assertFalse(gap.get("healthy"))

    def test_widget_empty_when_pending(self):
        w = collections_gap_widget(_bundle_pending())
        self.assertEqual(w.get("id"), "softdent-collections-gap")
        self.assertEqual(w.get("status"), "empty")
        self.assertEqual(w.get("gapCode"), GAP_COLLECTIONS_PENDING)

    def test_import_health_alert(self):
        alert = import_health_collections_alert(_bundle_pending())
        self.assertIsNotNone(alert)
        self.assertEqual(alert.get("id"), "def-001-collections-gap")
        health = assess_import_health(_bundle_pending())
        ids = [a.get("id") for a in (health.get("alerts") or []) if isinstance(a, dict)]
        self.assertIn("def-001-collections-gap", ids)

    def test_revenue_composition_stamps_gap(self):
        w = build_revenue_composition(_bundle_pending())
        self.assertEqual(w.get("status"), "empty")
        self.assertEqual(w.get("gapCode"), GAP_COLLECTIONS_PENDING)
        self.assertEqual(w.get("def"), "DEF-001")

    def test_hal_why_collections(self):
        from unittest import mock

        with mock.patch(
            "apex_backend._load_reports_and_bundle",
            return_value=({}, _bundle_pending(), None),
        ):
            r = resolve_hal_board_actions({"query": "why are collections empty?", "page": "hal"})
        self.assertTrue(r.get("handled"))
        reply = str(r.get("reply") or "")
        self.assertIn("DEF-001", reply)
        actions = r.get("actions") or []
        self.assertTrue(any(a.get("widgetId") == "softdent-collections-gap" for a in actions))

    def test_softdent_page_has_gap_widget(self):
        out = build_apex_widgets("softdent")
        ids = {w.get("id") for w in (out.get("widgets") or []) if isinstance(w, dict)}
        self.assertIn("softdent-collections-gap", ids)

    def test_format_reply(self):
        text = format_collections_gap_reply(assess_collections_gap(_bundle_pending()))
        self.assertIn("not $0", text.lower().replace("≠", "not "))
        self.assertIn("COLLECTIONS_PENDING", text)


if __name__ == "__main__":
    unittest.main()
