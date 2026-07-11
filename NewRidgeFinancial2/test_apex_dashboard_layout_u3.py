"""Phase U3 validation — dashboard layout schema (no Ollama)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID, build_apex_widgets
from apex_dashboard_layout_pack import (
    get_layout,
    layout_enabled,
    order_widget_specs,
    reset_layout,
    save_layout,
    sanitize_layout,
)


class DashboardLayoutPhaseU3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.store = Path(self._tmpdir.name) / "layouts.json"
        self._prev = os.environ.get("NR2_LAYOUT_STORE")
        os.environ["NR2_LAYOUT_STORE"] = str(self.store)

    def tearDown(self) -> None:
        if self._prev is None:
            os.environ.pop("NR2_LAYOUT_STORE", None)
        else:
            os.environ["NR2_LAYOUT_STORE"] = self._prev
        try:
            self._tmpdir.cleanup()
        except Exception:
            pass

    def test_build_id(self):
        self.assertEqual(BUILD_ID, "hal-10498")

    def test_flag_default_on(self):
        prev = os.environ.pop("NR2_DASHBOARD_LAYOUT", None)
        try:
            self.assertTrue(layout_enabled())
        finally:
            if prev is not None:
                os.environ["NR2_DASHBOARD_LAYOUT"] = prev

    def test_default_layout(self):
        got = get_layout("financial")
        self.assertTrue(got.get("ok"))
        self.assertTrue(got.get("default"))
        layout = got.get("layout") or {}
        self.assertEqual(layout.get("theme"), "starship-bridge")
        self.assertTrue(layout.get("grid"))

    def test_save_and_order(self):
        layout = sanitize_layout(
            {
                "grid": [
                    {"id": "b-widget", "order": 0, "w": 6},
                    {"id": "a-widget", "order": 1, "w": 6},
                ]
            },
            page="financial",
        )
        saved = save_layout(layout, page="financial")
        self.assertTrue(saved.get("ok"))
        specs = [{"id": "a-widget"}, {"id": "b-widget"}, {"id": "z-other"}]
        ordered = order_widget_specs(specs, page="financial")
        self.assertEqual([s["id"] for s in ordered[:2]], ["b-widget", "a-widget"])
        self.assertEqual(ordered[-1]["id"], "z-other")
        self.assertIn("layout", ordered[0])

    def test_sanitize_rejects_bad_ids(self):
        layout = sanitize_layout(
            {"grid": [{"id": "<script>", "w": 6}, {"id": "ok-id", "w": 99}]},
            page="softdent",
        )
        ids = [c["id"] for c in layout["grid"]]
        self.assertEqual(ids, ["ok-id"])
        self.assertEqual(layout["grid"][0]["w"], 12)

    def test_reset(self):
        save_layout({"grid": [{"id": "x", "order": 0}]}, page="financial")
        reset = reset_layout("financial")
        self.assertTrue(reset.get("ok"))
        self.assertTrue(reset.get("default"))

    def test_widget_present(self):
        out = build_apex_widgets("financial")
        ids = [w.get("id") for w in (out.get("widgets") or []) if isinstance(w, dict)]
        self.assertIn("dashboard-layout-status", ids)
        # U3-ordered ids from default should appear before unknowns when present
        if "hal-ai-insight" in ids and "deep-audit-status" in ids:
            self.assertLess(ids.index("hal-ai-insight"), ids.index("deep-audit-status"))


if __name__ == "__main__":
    unittest.main()
