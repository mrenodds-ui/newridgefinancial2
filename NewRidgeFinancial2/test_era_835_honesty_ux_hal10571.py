"""Moonshot ERA-835 Collections Honesty UX Bridge (hal-10576)."""

from __future__ import annotations

import unittest

from apex_backend import BUILD_ID
from nr2_contracts.softdent_hardening import (
    GAP_ERA_835_REQUIRED,
    assess_collections_gap,
    format_collections_gap_reply,
)
from softdent_practice_exports import stub_era835_ingestion_path


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


class Era835HonestyUxTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10576")

    def test_era_fallback_when_register_zero_insurance(self) -> None:
        gap = assess_collections_gap(_bundle_register_ins_plan_zero())
        # Ins Plan $0 is SoftDent truth → ERA path, not Collections-format re-export.
        self.assertFalse(gap.get("collectionsFormatRequired"))
        self.assertEqual(gap.get("collectionsGapCode"), GAP_ERA_835_REQUIRED)
        self.assertTrue(gap.get("registerInsPlanZero"))
        self.assertFalse(gap.get("collectionsExportRequired"))
        # Never invent insurance/patient dollars
        self.assertIn(gap.get("insurance"), (0.0, 0, None))
        text = format_collections_gap_reply(gap)
        self.assertIn("Ins Plan Collections $0.00", text)
        self.assertIn("ERA-835", text)
        self.assertIn("Do not re-export", text)
        # Must not recommend re-export as the remedial fix
        self.assertNotRegex(
            text,
            r"(?i)(?<!do not )(?<!don't )re-export.{0,40}register.{0,40}(to (fix|get|obtain)|and save)",
        )

    def test_hal_policy_july_insurance(self) -> None:
        from nr2_hal_gateway import try_local_policy_reply
        from unittest import mock

        with mock.patch(
            "apex_backend._load_reports_and_bundle",
            return_value=({}, _bundle_register_ins_plan_zero(), None),
        ):
            hit = try_local_policy_reply("What are July 2026 insurance collections?")
        self.assertIsNotNone(hit)
        text = (hit or {}).get("text") or ""
        self.assertIn("Ins Plan Collections $0.00", text)
        self.assertIn("ERA-835", text)
        self.assertIn("Do not re-export", text)

    def test_era_stub_readonly(self) -> None:
        stub = stub_era835_ingestion_path()
        self.assertTrue(stub.get("ok"))
        self.assertTrue(stub.get("readOnly"))
        self.assertFalse(stub.get("writeBack"))
        self.assertIn("ERA-835", stub.get("hint") or "")


if __name__ == "__main__":
    unittest.main()
