"""HAL money beam attestation + honesty gate — empty ≠ $0 (no invented currency)."""

from __future__ import annotations

import unittest
from unittest.mock import patch


def _live_attest_patches():
    return (
        patch(
            "hal_brain_tools.softdent_status",
            return_value={
                "hasData": True,
                "display": "$7,714",
                "hint": "SoftDent claims live",
                "totalOutstanding": 7714.0,
                "at": "2026-07-15T20:00:00+00:00",
            },
        ),
        patch(
            "hal_brain_tools.qb_summary",
            return_value={
                "hasData": True,
                "display": "$78,399",
                "hint": "QuickBooks revenue live (latest month)",
                "monthlyRevenue": 78399.0,
                "at": "2026-07-15T20:00:00+00:00",
            },
        ),
    )


class HalMoneyBeamAttestationTests(unittest.TestCase):
    def test_prompt_block_says_no_signal_when_beams_empty(self) -> None:
        from hal_brain_tools import money_beam_attestation

        with (
            patch(
                "hal_brain_tools.softdent_status",
                return_value={
                    "hasData": False,
                    "display": "∅ NO SIGNAL",
                    "hint": "empty ≠ $0 — SoftDent claims beam empty",
                    "totalOutstanding": None,
                },
            ),
            patch(
                "hal_brain_tools.qb_summary",
                return_value={
                    "hasData": False,
                    "display": "∅ NO SIGNAL",
                    "hint": "empty ≠ $0 — QB revenue beam empty",
                    "monthlyRevenue": None,
                },
            ),
        ):
            out = money_beam_attestation()
        self.assertTrue(out.get("ok"))
        self.assertTrue(out.get("emptyNotZero"))
        block = out.get("promptBlock") or ""
        self.assertIn("∅ NO SIGNAL", block)
        self.assertIn("never $0", block.lower())

    def test_prompt_block_cites_live_displays(self) -> None:
        from hal_brain_tools import money_beam_attestation

        with (
            patch(
                "hal_brain_tools.softdent_status",
                return_value={
                    "hasData": True,
                    "display": "$12,345",
                    "hint": "SoftDent claims live",
                    "totalOutstanding": 12345.0,
                },
            ),
            patch(
                "hal_brain_tools.qb_summary",
                return_value={
                    "hasData": True,
                    "display": "$78,399",
                    "hint": "QuickBooks revenue live (latest month)",
                    "monthlyRevenue": 78399.22,
                },
            ),
        ):
            out = money_beam_attestation()
        block = out.get("promptBlock") or ""
        self.assertIn("$12,345", block)
        self.assertIn("$78,399", block)
        self.assertNotIn("HONESTY:", block)
        self.assertTrue(out.get("beamHash"))
        self.assertIn(12345.0, out.get("allowedAmounts") or [])


class HalMoneyHonestyGateTests(unittest.TestCase):
    def test_is_money_query(self) -> None:
        from hal_brain_tools import is_money_query

        self.assertTrue(is_money_query("What is our AR?"))
        self.assertTrue(is_money_query("How much revenue last month?"))
        self.assertFalse(is_money_query("Open SoftDent page"))

    def test_deterministic_ar_cites_beam(self) -> None:
        from hal_brain_tools import money_beam_attestation, try_deterministic_money_reply

        with _live_attest_patches()[0], _live_attest_patches()[1]:
            att = money_beam_attestation()
            out = try_deterministic_money_reply("What is our outstanding AR?", att)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertTrue(out.get("moneyGrounded"))
        self.assertIn("$7,714", out.get("text") or "")
        self.assertIn("SoftDent", out.get("text") or "")

    def test_validate_rewrites_invented_dollars(self) -> None:
        from hal_brain_tools import money_beam_attestation, validate_money_reply

        with _live_attest_patches()[0], _live_attest_patches()[1]:
            att = money_beam_attestation()
            out = validate_money_reply(
                "AR is about $35,842 today.",
                query="What is our AR?",
                attest=att,
            )
        self.assertTrue(out.get("violation"))
        self.assertTrue(out.get("rewritten"))
        text = out.get("text") or ""
        self.assertNotIn("35,842", text)
        self.assertTrue("$7,714" in text or "unavailable" in text.lower())

    def test_validate_allows_live_beam_amount(self) -> None:
        from hal_brain_tools import money_beam_attestation, validate_money_reply

        with _live_attest_patches()[0], _live_attest_patches()[1]:
            att = money_beam_attestation()
            out = validate_money_reply(
                "$7,714 outstanding (SoftDent live).",
                query="What is our AR?",
                attest=att,
            )
        self.assertFalse(out.get("violation"))
        self.assertTrue(out.get("moneyGrounded"))

    def test_session_extra_fields(self) -> None:
        from hal_brain_tools import money_honesty_session_extra

        extra = money_honesty_session_extra(
            {
                "moneyGrounded": True,
                "beamTimestamp": "t1",
                "beamHash": "abc",
                "violation": True,
                "rewritten": True,
            }
        )
        self.assertTrue(extra.get("moneyGrounded"))
        self.assertEqual(extra.get("beamHash"), "abc")
        self.assertTrue(extra.get("moneyHonestyViolation"))


if __name__ == "__main__":
    unittest.main()
