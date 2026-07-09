"""Gateway local policy — consent, navigation, yes/no before model calls."""

from __future__ import annotations

import unittest

from nr2_hal_gateway import clean_gateway_text, extract_ollama_message_text, try_local_policy_reply


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

    def test_clean_gateway_strips_think_and_cot(self) -> None:
        cleaned = clean_gateway_text(
            "<think>secret</think>Okay, the user is asking about lag.\n\n"
            "Insurance lag is the main cash-flow risk — review denials next."
        )
        self.assertNotIn("secret", cleaned)
        self.assertFalse(cleaned.lower().startswith("okay, the user"))
        self.assertIn("Insurance lag", cleaned)

    def test_clean_gateway_strips_mid_body_cot(self) -> None:
        cleaned = clean_gateway_text(
            "Deposits can lag when SoftDent and QuickBooks disagree.\n"
            "Hmm, the user wants a deeper look at timing.\n"
            "Next step: reconcile the deposit batch."
        )
        self.assertNotIn("the user wants", cleaned.lower())
        self.assertIn("Deposits can lag", cleaned)
        self.assertIn("reconcile", cleaned.lower())

    def test_clean_gateway_strips_structured_plan_opener(self) -> None:
        cleaned = clean_gateway_text(
            "Here is a structured plan: Reconcile deposits, then review denials.",
            query="Why might deposits disagree?",
        )
        self.assertFalse(cleaned.lower().startswith("here is a structured plan"))
        self.assertIn("Reconcile deposits", cleaned)

    def test_extract_prefers_content_over_thinking(self) -> None:
        text = extract_ollama_message_text(
            {"content": "Yes. Imports stay read-only.", "thinking": "Okay let me think about tools."}
        )
        self.assertEqual(text, "Yes. Imports stay read-only.")


if __name__ == "__main__":
    unittest.main()
