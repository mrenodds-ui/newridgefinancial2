"""Gateway local policy — consent, navigation, yes/no before model calls."""

from __future__ import annotations

import json
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
        reply = try_local_policy_reply("What is insurance lag and why does cash flow suffer?")
        self.assertIsNone(reply)

    def test_hal_two_sentence_summary_local(self) -> None:
        reply = try_local_policy_reply("Summarize what HAL does in this program in two sentences.")
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertEqual(reply["intent"], "policy:hal-summary")
        self.assertIn("read-only", reply["text"].lower())

    def test_unknown_carc_refused(self) -> None:
        reply = try_local_policy_reply("What does CARC ZZ-9999 mean?")
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertEqual(reply["intent"], "policy:carc-unknown")
        self.assertIn("will not invent", reply["text"].lower())
        self.assertIn("escalate to posting supervisor", reply["text"].lower())

    def test_known_carc_co45_from_whitelist(self) -> None:
        reply = try_local_policy_reply("What does CARC CO-45 mean?")
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertEqual(reply["text"], "Contractual obligation; do not bill patient.")
        self.assertEqual(reply["intent"], "policy:carc-co-45")

    def test_write_softdent_preflight(self) -> None:
        reply = try_local_policy_reply("Can you modify the SoftDent fee schedule?")
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertEqual(reply["intent"], "consent:writeback-blocked")
        self.assertIn("read-only", reply["text"].lower())

    def test_empty_payroll_not_zero(self) -> None:
        reply = try_local_policy_reply("Is an empty payroll export the same as $0 wages?")
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertEqual(reply["intent"], "policy:empty-not-zero")

    def test_sentence_cap_applied(self) -> None:
        from nr2_hal_gateway import apply_response_constraints

        long = (
            "First point about lag. Second point about denials. "
            "Third point about deposits. Fourth point about aging."
        )
        capped = apply_response_constraints("Explain insurance lag in two sentences.", long)
        self.assertEqual(capped.count("."), 2)
        self.assertNotIn("Fourth", capped)

    def test_options_cap_short_asks(self) -> None:
        from nr2_hal_gateway import options_for_query

        opts = options_for_query("Yes or no: can you post to QuickBooks?")
        self.assertLessEqual(int(opts.get("num_predict") or 999), 128)

    def test_deliverable_request_detect(self) -> None:
        from nr2_hal_gateway import is_deliverable_request

        self.assertTrue(is_deliverable_request("What are the next steps to reconcile deposits?"))
        self.assertTrue(is_deliverable_request("How do I refresh SoftDent imports?"))
        self.assertFalse(is_deliverable_request("What is insurance lag?"))
        self.assertFalse(is_deliverable_request("Is step therapy common?"))

    def test_normalize_deliverable_json(self) -> None:
        from nr2_hal_gateway import normalize_deliverable_reply

        raw = json.dumps(
            {
                "steps": ["Open Claims.", "Verify the EOB line.", "Draft locally — do not invent dollars."],
                "caution": "NR2 stays read-only; staff posts in SoftDent.",
                "references": ["Claims"],
            }
        )
        out = normalize_deliverable_reply("What are the next steps for this denial?", raw)
        self.assertIn("1. Open Claims.", out)
        self.assertIn("Caution:", out)
        self.assertIn("References:", out)

    def test_normalize_deliverable_prose_fallback(self) -> None:
        from nr2_hal_gateway import normalize_deliverable_reply

        prose = "Open Claims. Verify the EOB. Draft the narrative locally."
        out = normalize_deliverable_reply("Walk me through the next steps.", prose)
        self.assertIn("1. Open Claims.", out)
        self.assertIn("2. Verify the EOB.", out)

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

    def test_extract_ignores_thinking_only(self) -> None:
        text = extract_ollama_message_text(
            {"content": "", "thinking": "Okay, the user is asking if I can post to QuickBooks."}
        )
        self.assertEqual(text, "")

    def test_hal_local_disables_think(self) -> None:
        from nr2_hal_gateway import _ollama_think_flag

        self.assertIs(False, _ollama_think_flag("hal-local:30b-a3b"))
        self.assertIs(False, _ollama_think_flag("qwen3:32b"))

    def test_imports_read_only(self) -> None:
        reply = try_local_policy_reply("Are imports read-only?")
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertTrue(reply["text"].lower().startswith("yes"))
        self.assertIn("read-only", reply["text"].lower())


if __name__ == "__main__":
    unittest.main()
