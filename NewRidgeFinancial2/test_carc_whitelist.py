"""Moonshot HAL 190Q Phase 4 — CARC/CAS whitelist hardening tests."""

from __future__ import annotations

import unittest

from apex_era835_pack import _enrich_adjustment_reasons_for_hal
from era835_parser import (
    CARC_BRIEFS,
    CARC_UNKNOWN_REFUSAL,
    CAS_BRIEFS,
    all_carc_briefs,
    enrich_codes_with_briefs,
    extract_carc_codes_from_text,
    format_carc_brief_reply,
    lookup_carc_brief,
)
from nr2_hal_gateway import try_local_policy_reply


class CarcWhitelistTests(unittest.TestCase):
    def test_whitelist_sizes(self) -> None:
        self.assertEqual(len(CARC_BRIEFS), 25)
        self.assertEqual(len(CAS_BRIEFS), 10)
        self.assertGreaterEqual(len(all_carc_briefs()), 35)

    def test_briefs_max_140_chars(self) -> None:
        for code, brief in all_carc_briefs().items():
            self.assertLessEqual(len(brief), 140, msg=f"{code} brief too long")

    def test_co45_exact_map_text(self) -> None:
        self.assertEqual(
            lookup_carc_brief("CO-45"),
            "Contractual obligation; do not bill patient.",
        )
        reply = try_local_policy_reply("What does CARC CO-45 mean?")
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertEqual(reply["intent"], "policy:carc-co-45")
        self.assertEqual(reply["text"], "Contractual obligation; do not bill patient.")

    def test_carc_45_shorthand_maps_to_co45(self) -> None:
        self.assertIn("CO-45", extract_carc_codes_from_text("What is CARC 45?"))
        reply = try_local_policy_reply("What is CARC 45?")
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertEqual(reply["text"], "Contractual obligation; do not bill patient.")

    def test_unknown_xx99_hard_refuse(self) -> None:
        reply = try_local_policy_reply("What does CARC XX-99 mean?")
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertEqual(reply["intent"], "policy:carc-unknown")
        self.assertIn(CARC_UNKNOWN_REFUSAL, reply["text"])
        self.assertIn("escalate to posting supervisor", reply["text"].lower())
        self.assertIn("will not invent", reply["text"].lower())

    def test_pr_staff_action_hint(self) -> None:
        brief = lookup_carc_brief("PR-2")
        self.assertIsNotNone(brief)
        assert brief is not None
        self.assertIn("Staff Action:", brief)
        reply = try_local_policy_reply("Explain CAS PR-2")
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertIn("Staff Action:", reply["text"])

    def test_enrich_absent_code_refuses(self) -> None:
        pack = enrich_codes_with_briefs(["CO-45", "XX-99"])
        self.assertIn("CO-45", pack["briefs"])
        self.assertIn("XX-99", pack["refused"])
        self.assertIn("escalate to posting supervisor", str(pack.get("refuseNote") or "").lower())

    def test_era_pack_injects_briefs(self) -> None:
        enriched = _enrich_adjustment_reasons_for_hal({"CO-45": 2, "ZZ-1": 1})
        self.assertEqual(
            enriched["briefs"]["CO-45"],
            "Contractual obligation; do not bill patient.",
        )
        self.assertIn("ZZ-1", enriched["refused"])
        self.assertTrue(enriched["knownOnly"])

    def test_format_carc_brief_reply_co45(self) -> None:
        self.assertEqual(
            format_carc_brief_reply("CO-45"),
            "Contractual obligation; do not bill patient.",
        )


if __name__ == "__main__":
    unittest.main()
