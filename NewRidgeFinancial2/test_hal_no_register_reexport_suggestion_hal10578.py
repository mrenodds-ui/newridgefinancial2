"""HAL Policy Hardening — forbid Register re-export when Ins Plan $0 (hal-10578)."""

from __future__ import annotations

import re
import unittest
from unittest import mock

from apex_softdent_hardening_pack import (
    GAP_ERA_835_REQUIRED,
    SUGGESTED_ACTION_ERA_835_PROCURE,
    SUGGESTED_ACTION_RE_EXPORT_REGISTER,
    assess_collections_gap,
    collections_gap_widget,
    format_collections_gap_reply,
    register_ins_plan_zero_blocks_reexport,
    reply_suggests_register_reexport,
    resolve_collections_suggested_action,
)


def _july_regular_complete_bundle() -> dict:
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
                        "insurance": 0.0,
                        "patient": 30626.42,
                        "regularCollections": 30626.42,
                        "regularCollectionsReported": True,
                        "registerInsPlanZero": True,
                        "insuranceSplitReported": True,
                    }
                ]
            }
        }
    }


class HalNoRegisterReexportHal10578Tests(unittest.TestCase):
    def test_hal_no_register_reexport_suggestion_hal10578(self) -> None:
        gap = assess_collections_gap(_july_regular_complete_bundle())
        self.assertTrue(gap.get("registerInsPlanZero"))
        self.assertEqual(gap.get("collectionsGapCode"), GAP_ERA_835_REQUIRED)
        self.assertEqual(gap.get("suggestedAction"), SUGGESTED_ACTION_ERA_835_PROCURE)
        self.assertNotEqual(gap.get("suggestedAction"), SUGGESTED_ACTION_RE_EXPORT_REGISTER)
        self.assertTrue(gap.get("forbidRegisterReexport"))
        self.assertTrue(register_ins_plan_zero_blocks_reexport(gap))

        text = format_collections_gap_reply(gap)
        self.assertIn("Do not re-export", text)
        self.assertIn("suggestedAction=`era_835_procure`", text)
        self.assertIn("Regular Collections: Complete", text)
        self.assertFalse(reply_suggests_register_reexport(text))
        self.assertNotRegex(text, r"(?i)suggestedAction[`'\"=\s:]*re_export_register")

        w = collections_gap_widget(_july_regular_complete_bundle())
        self.assertEqual(w.get("suggestedAction"), SUGGESTED_ACTION_ERA_835_PROCURE)
        self.assertTrue(w.get("forbidRegisterReexport"))
        msg = w.get("message") or ""
        self.assertIn("Regular Collections: Complete", msg)
        self.assertIn("ERA Required", msg)
        # Gap-tile chips must not ask for Register re-export
        chip_blob = " ".join(
            f"{c.get('label')} {c.get('query')}" for c in (w.get("halChips") or [])
        )
        self.assertFalse(re.search(r"(?i)re-?export.*register|register.*re-?export", chip_blob))

        from nr2_hal_gateway import try_local_policy_reply

        with mock.patch(
            "apex_backend._load_reports_and_bundle",
            return_value=({}, _july_regular_complete_bundle(), None),
        ):
            hit = try_local_policy_reply("What are July 2026 insurance collections?")
            refuse = try_local_policy_reply(
                "Should I re-export the July Register hoping Ins Plan > 0?"
            )

        self.assertIsNotNone(hit)
        self.assertEqual((hit or {}).get("suggestedAction"), SUGGESTED_ACTION_ERA_835_PROCURE)
        hit_text = (hit or {}).get("text") or ""
        self.assertIn("Ins Plan Collections $0.00", hit_text)
        self.assertFalse(reply_suggests_register_reexport(hit_text))

        self.assertIsNotNone(refuse)
        self.assertEqual((refuse or {}).get("intent"), "policy:forbid-register-reexport")
        self.assertEqual(
            (refuse or {}).get("suggestedAction"), SUGGESTED_ACTION_ERA_835_PROCURE
        )
        refuse_text = (refuse or {}).get("text") or ""
        self.assertIn("Refused", refuse_text)
        self.assertNotIn(SUGGESTED_ACTION_RE_EXPORT_REGISTER, refuse_text)

    def test_resolve_never_emits_reexport_on_ins_plan_zero(self) -> None:
        gap = {
            "registerInsPlanZero": True,
            "regularCollectionsReported": True,
            "collectionsGapCode": GAP_ERA_835_REQUIRED,
            "healthy": False,
        }
        self.assertEqual(
            resolve_collections_suggested_action(gap), SUGGESTED_ACTION_ERA_835_PROCURE
        )


if __name__ == "__main__":
    unittest.main()
