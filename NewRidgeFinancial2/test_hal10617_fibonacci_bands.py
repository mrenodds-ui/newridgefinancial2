"""nr2-11000-clean — mosaic / Fibonacci band packing retired; stacked stage only."""

from __future__ import annotations

import os
import unittest

from apex_backend import BUILD_ID, build_apex_widgets, _WIDGETS_CACHE


class Hal10617StackNoMosaicTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(BUILD_ID, "nr2-11000-clean")

    def test_pages_emit_no_mosaic_layout(self) -> None:
        prev = os.environ.get("NR2_APEX_BLANK_WIDGETS")
        os.environ["NR2_APEX_BLANK_WIDGETS"] = "0"
        try:
            _WIDGETS_CACHE.clear()
            pages = (
                "financial",
                "taxes",
                "softdent",
                "claims",
                "ar",
                "quickbooks",
                "office-manager",
                "hal",
            )
            for page in pages:
                payload = build_apex_widgets(page, _fill=True)
                self.assertEqual(payload.get("buildId"), "nr2-11000-clean", page)
                self.assertIsNone(payload.get("mosaicLayout"), page)
                widgets = payload.get("widgets") or []
                tiled = [
                    w
                    for w in widgets
                    if isinstance(w, dict) and (w.get("tileClass") or w.get("band") or w.get("mosaicBand"))
                ]
                self.assertEqual(tiled, [], page)
        finally:
            if prev is None:
                os.environ.pop("NR2_APEX_BLANK_WIDGETS", None)
            else:
                os.environ["NR2_APEX_BLANK_WIDGETS"] = prev
            _WIDGETS_CACHE.clear()

    def test_ops_also_unbanded(self) -> None:
        prev = os.environ.get("NR2_APEX_BLANK_WIDGETS")
        os.environ["NR2_APEX_BLANK_WIDGETS"] = "0"
        try:
            _WIDGETS_CACHE.clear()
            payload = build_apex_widgets("softdent", sub="ops", _fill=True)
            self.assertIsNone(payload.get("mosaicLayout"))
        finally:
            if prev is None:
                os.environ.pop("NR2_APEX_BLANK_WIDGETS", None)
            else:
                os.environ["NR2_APEX_BLANK_WIDGETS"] = prev
            _WIDGETS_CACHE.clear()


if __name__ == "__main__":
    unittest.main()
