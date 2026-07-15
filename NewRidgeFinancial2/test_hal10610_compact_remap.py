"""hal-10610 — Compact widgets remap (32B consult apply).

Taxes: planning table/calendar off main → #taxes/planning + tax-core-strip.
Financial: efficiency pill removed (radial-gauge only).
SoftDent: ops chips strip-sized; no redundant operatory when chairs in vitals.
Claims: aging exposure m; no critical-actions duplicate when Top 5 present.
"""

from __future__ import annotations

import unittest

from apex_backend import BUILD_ID, build_apex_widgets
from apex_financial_console_pack import build_financial_vital_signs
from apex_subpages_wave5_pack import build_taxes_planning


class Hal10610CompactRemapTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10631")

    def test_taxes_main_moves_planning_to_subpage(self) -> None:
        out = build_apex_widgets("taxes", _fill=True)
        ids = [w.get("id") for w in out.get("widgets") or [] if isinstance(w, dict)]
        self.assertNotIn("tax-planning-table", ids)
        self.assertNotIn("tax-calendar-main", ids)
        self.assertIn("tax-core-strip", ids)
        self.assertIn("tax-open-planning", ids)

    def test_taxes_planning_subpage_has_table_and_calendar(self) -> None:
        widgets = build_taxes_planning({}, {})
        ids = [w.get("id") for w in widgets if isinstance(w, dict)]
        self.assertIn("tax-planning-table", ids)
        self.assertIn("tax-calendar-main", ids)

    def test_financial_vitals_no_efficiency_pill(self) -> None:
        vitals = build_financial_vital_signs({}, {})
        pills = vitals.get("pills") if isinstance(vitals.get("pills"), list) else []
        pill_ids = [p.get("id") for p in pills if isinstance(p, dict)]
        self.assertNotIn("collection-bullet", pill_ids)
        self.assertIn("prod-mtd", pill_ids)
        self.assertIn("ar-outstanding", pill_ids)
        self.assertLessEqual(len(pills), 4)

    def test_claims_aging_is_compact(self) -> None:
        out = build_apex_widgets("claims", _fill=True)
        aging = next(
            (
                w
                for w in (out.get("widgets") or [])
                if isinstance(w, dict) and w.get("id") == "claims-aging-exposure"
            ),
            None,
        )
        if aging is None:
            self.skipTest("claims-aging-exposure not emitted without claims import")
        self.assertEqual(aging.get("size"), "m")
        ids = [w.get("id") for w in out.get("widgets") or [] if isinstance(w, dict)]
        # Top-critical path should omit duplicate critical-actions widget
        if "claims-top-critical" in ids:
            self.assertNotIn("claims-critical-actions", ids)

    def test_softdent_tp_is_strip(self) -> None:
        from softdent_treatment_planning import treatment_plan_estimate_widget

        w = treatment_plan_estimate_widget()
        self.assertEqual(w.get("size"), "strip")
        self.assertEqual(w.get("maxHeight"), 80)


if __name__ == "__main__":
    unittest.main()
