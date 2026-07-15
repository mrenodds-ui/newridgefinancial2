"""hal-10628 — HAL medium spine: only full-stack instruments, ordered layout."""

from __future__ import annotations

import unittest

from apex_backend import BUILD_ID, build_apex_widgets, _WIDGETS_CACHE


class Hal10624MediumSpineTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10629")

    def test_hal_spine_order_and_ids(self) -> None:
        _WIDGETS_CACHE.clear()
        out = build_apex_widgets("hal", _fill=True)
        self.assertEqual(out.get("buildId"), "hal-10629")
        self.assertIsNone(out.get("mosaicLayout"))
        ids = [w.get("id") for w in (out.get("widgets") or []) if isinstance(w, dict)]
        self.assertIn("hal-ask", ids)
        self.assertIn("hal-import-health", ids)
        self.assertIn("hal-program-posture", ids)
        # Spine order: chat first (rail), then trust/insight
        self.assertEqual(ids[0], "hal-ask")
        self.assertLess(ids.index("hal-import-health"), ids.index("hal-program-posture"))
        # Dropped clutter / noise tiles
        for gone in (
            "hal-mosaic-prod",
            "hal-mosaic-coll",
            "hal-mosaic-ar",
            "hal-mosaic-claims",
            "hal-suggestion",
            "hal-categorize-assist",
            "hal-recommended-actions",
            "import-cache-kpi",
            "bridge-errors",
            "reconciliation-status",
        ):
            self.assertNotIn(gone, ids)
        # Medium chrome markers on trust pair
        by_id = {w.get("id"): w for w in (out.get("widgets") or []) if isinstance(w, dict)}
        self.assertEqual(by_id["hal-import-health"].get("chrome"), "hal-medium")
        self.assertEqual(by_id["hal-program-posture"].get("layoutRole"), "trust")


if __name__ == "__main__":
    unittest.main()
