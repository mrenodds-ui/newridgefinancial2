"""hal-10631 — blank widgets default ON; set NR2_APEX_BLANK_WIDGETS=0 to restore."""

from __future__ import annotations

import os
import unittest

from apex_backend import APEX_PAGES, BUILD_ID, build_apex_widgets, _WIDGETS_CACHE, _apex_blank_all_widgets


class Hal10619BlankWidgetsTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10631")

    def test_blank_default_on(self) -> None:
        prev = os.environ.get("NR2_APEX_BLANK_WIDGETS")
        try:
            os.environ.pop("NR2_APEX_BLANK_WIDGETS", None)
            self.assertTrue(_apex_blank_all_widgets())
        finally:
            if prev is None:
                os.environ.pop("NR2_APEX_BLANK_WIDGETS", None)
            else:
                os.environ["NR2_APEX_BLANK_WIDGETS"] = prev

    def test_blank_default_empties_every_page(self) -> None:
        prev = os.environ.get("NR2_APEX_BLANK_WIDGETS")
        try:
            os.environ.pop("NR2_APEX_BLANK_WIDGETS", None)
            _WIDGETS_CACHE.clear()
            for page in APEX_PAGES:
                out = build_apex_widgets(page, _fill=True)
                self.assertEqual(out.get("buildId"), "hal-10631", page)
                self.assertTrue(out.get("blankWidgets"), page)
                self.assertEqual(out.get("widgets"), [], page)
                self.assertIsNone(out.get("mosaicLayout"), page)
            ops = build_apex_widgets("softdent", sub="ops", _fill=True)
            self.assertEqual(ops.get("widgets"), [])
            self.assertTrue(ops.get("blankWidgets"))
        finally:
            if prev is None:
                os.environ.pop("NR2_APEX_BLANK_WIDGETS", None)
            else:
                os.environ["NR2_APEX_BLANK_WIDGETS"] = prev
            _WIDGETS_CACHE.clear()

    def test_opt_out_restores_widgets(self) -> None:
        prev = os.environ.get("NR2_APEX_BLANK_WIDGETS")
        os.environ["NR2_APEX_BLANK_WIDGETS"] = "0"
        try:
            _WIDGETS_CACHE.clear()
            self.assertFalse(_apex_blank_all_widgets())
            out = build_apex_widgets("financial", _fill=True)
            self.assertFalse(out.get("blankWidgets"))
            self.assertGreaterEqual(len(out.get("widgets") or []), 1)
        finally:
            if prev is None:
                os.environ.pop("NR2_APEX_BLANK_WIDGETS", None)
            else:
                os.environ["NR2_APEX_BLANK_WIDGETS"] = prev
            _WIDGETS_CACHE.clear()


if __name__ == "__main__":
    unittest.main()
