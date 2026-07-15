"""hal-10628 — omit helpers remain; live build no longer zero-scroll caps."""

from __future__ import annotations

import unittest

from apex_backend import BUILD_ID, build_apex_widgets, _WIDGETS_CACHE
from apex_compact_pages_pack import (
    OMIT_OPTIONAL_ZERO_SCROLL_IDS,
    omit_until_source_widgets,
    select_demoted_widgets,
)


class Hal10616ZeroScrollReorgTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10629")

    def test_optional_softDent_omitted_by_helper(self) -> None:
        widgets = [
            {"id": "softdent-gold-csv-drop-ops", "status": "warn", "type": "status"},
            {"id": "sd-vitals-strip", "status": "ok", "type": "executive-strip"},
            {"id": "hal-mosaic-prod", "status": "ok", "type": "kpi"},
            {"id": "claims-open-kanban", "status": "ok", "type": "status"},
        ]
        out = omit_until_source_widgets(widgets, page="softdent")
        ids = [w.get("id") for w in out if isinstance(w, dict)]
        self.assertEqual(ids, ["sd-vitals-strip"])
        for wid in OMIT_OPTIONAL_ZERO_SCROLL_IDS & {
            "softdent-gold-csv-drop-ops",
            "hal-mosaic-prod",
            "claims-open-kanban",
        }:
            self.assertNotIn(wid, ids)

    def test_live_build_is_uncapped(self) -> None:
        _WIDGETS_CACHE.clear()
        main = build_apex_widgets("softdent", _fill=True)
        ops = build_apex_widgets("softdent", sub="ops", _fill=True)
        main_ids = [w.get("id") for w in (main.get("widgets") or []) if isinstance(w, dict)]
        ops_ids = [w.get("id") for w in (ops.get("widgets") or []) if isinstance(w, dict)]
        self.assertGreaterEqual(len(main_ids), 1)
        self.assertIsInstance(ops_ids, list)
        self.assertIsNone(main.get("mosaicLayout"))

    def test_softdent_ops_helper_no_more_omitted_notice(self) -> None:
        widgets = [
            {"id": "softdent-aging-gap", "type": "status", "status": "ok"},
            {"id": "softdent-gold-payment-pipeline", "type": "status", "status": "warn"},
        ]
        ops = select_demoted_widgets(widgets, page="softdent")
        ids = [w.get("id") for w in ops if isinstance(w, dict)]
        self.assertIn("softdent-aging-gap", ids)
        self.assertNotIn("softdent-ops-more-omitted", ids)
        self.assertNotIn("softdent-gold-payment-pipeline", ids)


if __name__ == "__main__":
    unittest.main()
