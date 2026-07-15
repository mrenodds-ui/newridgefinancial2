"""hal-10628 — pack helpers still demote; live build no longer partitions."""

from __future__ import annotations

import unittest

from apex_backend import BUILD_ID, build_apex_widgets
from apex_compact_pages_pack import PAGE_FIRST_VIEW_KEEP, partition_first_viewport, select_demoted_widgets


class Hal10612DemoteOpsTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10631")

    def test_partition_keeps_only_allowlist(self) -> None:
        widgets = [
            {"id": "financial-command-strip", "type": "financial-command-strip", "label": "Cmd"},
            {"id": "ebitda-station", "type": "ebitda-station", "label": "EBITDA"},
            {"id": "expense-treemap", "type": "treemap", "label": "Expenses"},
            {"id": "financial-dual-trend", "type": "dual-axis-trend", "label": "Trend"},
        ]
        out = partition_first_viewport(widgets, page="financial")
        ids = [w.get("id") for w in out if isinstance(w, dict)]
        self.assertIn("financial-command-strip", ids)
        self.assertIn("financial-dual-trend", ids)
        self.assertNotIn("ebitda-station", ids)
        self.assertNotIn("expense-treemap", ids)
        self.assertIn("financial-ops-open", ids)

    def test_ops_subpage_has_demoted_ids(self) -> None:
        widgets = [
            {"id": "financial-command-strip", "type": "financial-command-strip"},
            {"id": "ebitda-station", "type": "ebitda-station", "label": "EBITDA"},
        ]
        ops = select_demoted_widgets(widgets, page="financial")
        ids = [w.get("id") for w in ops if isinstance(w, dict)]
        self.assertIn("ebitda-station", ids)
        self.assertNotIn("financial-command-strip", ids)
        self.assertIn("financial-overview-open", ids)

    def test_live_build_does_not_partition(self) -> None:
        out = build_apex_widgets("financial", _fill=True)
        self.assertIsNone(out.get("mosaicLayout"))
        widgets = [w for w in (out.get("widgets") or []) if isinstance(w, dict)]
        self.assertGreaterEqual(len(widgets), 1)
        # Free stage may exceed the old first-viewport keep set.
        self.assertTrue(len(widgets) >= 1)
        _ = PAGE_FIRST_VIEW_KEEP["financial"]

    def test_financial_ops_subpage_exists(self) -> None:
        out = build_apex_widgets("financial", sub="ops", _fill=True)
        self.assertEqual(out.get("sub"), "ops")
        ids = [w.get("id") for w in (out.get("widgets") or []) if isinstance(w, dict)]
        self.assertTrue(len(ids) >= 1)

    def test_empty_not_padded_to_zero(self) -> None:
        widgets = [
            {"id": "ebitda-station", "type": "ebitda-station", "status": "empty", "value": None, "label": "EBITDA"},
        ]
        ops = select_demoted_widgets(widgets, page="financial")
        gap = next((w for w in ops if isinstance(w, dict) and w.get("id") == "ebitda-station"), None)
        self.assertIsNotNone(gap)
        self.assertNotEqual(gap.get("value"), 0)
        self.assertNotEqual(gap.get("value"), "$0")


if __name__ == "__main__":
    unittest.main()
