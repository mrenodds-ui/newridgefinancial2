"""Moonshot gap-tile honesty label polish (hal-10576)."""

from __future__ import annotations

import unittest
from unittest import mock

from apex_backend import BUILD_ID
from nr2_contracts.softdent_hardening import (
    GAP_ERA_835_REQUIRED,
    assess_collections_gap,
    collections_gap_widget,
    display_collections_gap_code,
)
from nr2_contracts.softdent_era import GAP_ERA_835_AVAILABLE, enrich_collections_gap_with_era


def _bundle_register_ins_plan_zero() -> dict:
    return {
        "softdent": {
            "dashboard": {
                "rows": [
                    {
                        "period": "2026-07",
                        "year_month": "2026-07",
                        "production": 44735.0,
                        "collections": 30626.42,
                        "collectionsReported": True,
                        "collectionsPending": False,
                        "collectionsFormatRequired": True,
                        "insurance": 0.0,
                        "patient": 0.0,
                    }
                ]
            }
        }
    }


class GapTileEraRequiredLabelTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10576")

    def test_widget_message_surfaces_required_not_available(self) -> None:
        w = collections_gap_widget(_bundle_register_ins_plan_zero())
        self.assertEqual(w.get("id"), "softdent-collections-gap")
        self.assertEqual(w.get("emptyMessage"), GAP_ERA_835_REQUIRED)
        self.assertEqual(w.get("gapCode"), GAP_ERA_835_REQUIRED)
        self.assertIn(GAP_ERA_835_REQUIRED, str(w.get("message") or ""))
        self.assertNotIn(GAP_ERA_835_AVAILABLE, str(w.get("message") or ""))
        hint = str(w.get("hint") or "")
        self.assertIn("Ins Plan Collections $0.00", hint)
        self.assertIn("Do not re-export", hint)
        labels = [c.get("label") for c in (w.get("halChips") or [])]
        self.assertTrue(any("ERA-835 path" in str(lab) for lab in labels))
        self.assertTrue(all("re-export" not in str(c).lower() for c in (w.get("halChips") or [])))

    def test_enrich_preserves_required_when_register_ins_zero(self) -> None:
        gap = {
            "gapCode": GAP_ERA_835_REQUIRED,
            "collectionsGapCode": GAP_ERA_835_REQUIRED,
            "registerInsPlanZero": True,
            "period": "2026-07",
            "healthy": False,
            "collections": None,
            "issues": [],
        }
        with mock.patch(
            "nr2_contracts.softdent_era.era_available_for_period",
            return_value={"available": True, "paymentTotal": None, "claimCount": 4},
        ):
            enriched = enrich_collections_gap_with_era(gap)
        self.assertEqual(enriched.get("gapCode"), GAP_ERA_835_REQUIRED)
        self.assertEqual(enriched.get("collectionsGapCode"), GAP_ERA_835_REQUIRED)
        self.assertEqual(enriched.get("eraGapCode"), GAP_ERA_835_AVAILABLE)
        self.assertTrue(enriched.get("eraAvailable"))
        self.assertEqual(display_collections_gap_code(enriched), GAP_ERA_835_REQUIRED)

    def test_assess_live_display_code(self) -> None:
        gap = assess_collections_gap(_bundle_register_ins_plan_zero())
        self.assertEqual(gap.get("collectionsGapCode"), GAP_ERA_835_REQUIRED)
        self.assertEqual(display_collections_gap_code(gap), GAP_ERA_835_REQUIRED)


if __name__ == "__main__":
    unittest.main()
