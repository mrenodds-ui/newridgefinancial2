"""HAL money beam attestation — empty ≠ $0 (no invented currency)."""

from __future__ import annotations

import unittest
from unittest.mock import patch


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


if __name__ == "__main__":
    unittest.main()
