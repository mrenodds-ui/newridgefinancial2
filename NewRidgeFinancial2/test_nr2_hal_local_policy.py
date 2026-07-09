"""Gateway local policy — consent, navigation, yes/no before model calls."""

from __future__ import annotations

import unittest

from nr2_hal_gateway import try_local_policy_reply


class HalLocalPolicyTests(unittest.TestCase):
    def test_navigation_claims(self) -> None:
        reply = try_local_policy_reply("Open the Claims page.")
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertTrue(reply["text"].lower().startswith("yes"))
        self.assertIn("claims", reply["text"].lower())
        self.assertEqual(reply["intent"], "navigate:claims")

    def test_email_without_consent_blocked(self) -> None:
        reply = try_local_policy_reply("Can you email the payer without consent?")
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertTrue(reply["text"].lower().startswith("no"))
        self.assertEqual(reply["intent"], "consent:required")

    def test_post_quickbooks_blocked(self) -> None:
        reply = try_local_policy_reply("Can you post to QuickBooks?")
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertTrue(reply["text"].lower().startswith("no"))

    def test_payer_submit_yes_no(self) -> None:
        reply = try_local_policy_reply("Yes or no: can HAL submit claims to the portal?")
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertTrue(reply["text"].lower().startswith("no"))

    def test_general_question_not_intercepted(self) -> None:
        reply = try_local_policy_reply("Summarize what HAL does in this program in two sentences.")
        self.assertIsNone(reply)


if __name__ == "__main__":
    unittest.main()
