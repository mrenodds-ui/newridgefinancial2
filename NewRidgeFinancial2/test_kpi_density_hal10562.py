"""Moonshot KPI density (hal-10576) — page-level smoke."""

from __future__ import annotations

import unittest

from apex_backend import BUILD_ID, build_apex_widgets


class KpiDensityPageTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10576")

    def _kpi_tiles(self, widgets: list) -> list:
        return [
            w
            for w in widgets
            if isinstance(w, dict)
            and w.get("type") == "kpi"
            and not w.get("kpiOverBudget")
        ]

    def test_taxes_main_no_planning_kpi_warehouse(self) -> None:
        out = build_apex_widgets("taxes", _fill=True)
        widgets = out.get("widgets") or []
        kpis = self._kpi_tiles(widgets)
        self.assertLessEqual(len(kpis), 4, f"taxes main KPIs={ [k.get('id') for k in kpis] }")
        ids = {w.get("id") for w in widgets if isinstance(w, dict)}
        self.assertIn("tax-year-status", ids)
        self.assertIn("tax-open-planning", ids)
        # Planning money KPIs must not flood main
        for banned in ("tax-est-owner", "tax-k1-ordinary", "tax-modeled-w2", "tax-federal-est"):
            self.assertNotIn(banned, ids)

    def test_taxes_planning_subpage_has_estimates(self) -> None:
        out = build_apex_widgets("taxes", sub="planning", _fill=True)
        self.assertEqual(out.get("sub"), "planning")
        widgets = out.get("widgets") or []
        ids = {w.get("id") for w in widgets if isinstance(w, dict)}
        self.assertTrue(
            "tax-book-net" in ids or "tax-est-owner" in ids or any("planning" in str(i) for i in ids),
            f"planning subpage ids={ids}",
        )

    def test_softdent_uses_vitals_strip(self) -> None:
        out = build_apex_widgets("softdent", _fill=True)
        widgets = out.get("widgets") or []
        ids = {w.get("id") for w in widgets if isinstance(w, dict)}
        self.assertIn("sd-vitals-strip", ids)
        kpis = self._kpi_tiles(widgets)
        self.assertLessEqual(len(kpis), 4, f"softdent KPIs={ [k.get('id') for k in kpis] }")

    def test_financial_ops_strip(self) -> None:
        out = build_apex_widgets("financial", _fill=True)
        widgets = out.get("widgets") or []
        ids = {w.get("id") for w in widgets if isinstance(w, dict)}
        self.assertIn("financial-ops-strip", ids)
        # Secondary claims/tx KPIs packed — not separate tiles
        for banned in ("treatment-plans", "case-acceptance"):
            standalone = [
                w
                for w in widgets
                if isinstance(w, dict) and w.get("id") == banned and w.get("type") == "kpi"
            ]
            self.assertEqual(standalone, [])

    def test_source_note_mentions_kpi_density(self) -> None:
        out = build_apex_widgets("taxes", _fill=True)
        self.assertIn("kpi-density", str(out.get("sourceNote") or ""))


if __name__ == "__main__":
    unittest.main()
