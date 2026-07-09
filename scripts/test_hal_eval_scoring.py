"""Unit tests for shared HAL eval scoring helpers."""

from __future__ import annotations

import unittest

from hal_eval_scoring import score_answer


class HalEvalScoringTests(unittest.TestCase):
    def test_yes_no_readonly_quality(self) -> None:
        score = score_answer(
            "Can you post to QuickBooks?",
            "No — I cannot post to QuickBooks from here; this stays read-only. Staff clicks Post after review.",
        )
        self.assertTrue(score["hasYesNoLead"])
        self.assertTrue(score["hasReadOnlyMention"])
        self.assertTrue(score["hasDirectAnswer"])
        self.assertTrue(score["qualityPass"])

    def test_cot_and_plan_opener_fail(self) -> None:
        score = score_answer(
            "Why might deposits disagree?",
            "Here is a structured plan:\nOkay, the user is asking about deposits.\n\nNext step: reconcile.",
        )
        self.assertTrue(score["hasStructuredPlanOpener"])
        self.assertTrue(score["hasCotLeak"])
        self.assertFalse(score["qualityPass"])

    def test_consent_required(self) -> None:
        score = score_answer(
            "Can you email the payer without consent?",
            "No — I won't email the payer without explicit consent. I can draft locally first.",
        )
        self.assertTrue(score["hasConsentMention"])
        self.assertTrue(score["qualityPass"])

    def test_mid_body_cot_fails(self) -> None:
        score = score_answer(
            "Why might deposits disagree?",
            "Deposits can lag. Hmm, the user wants a deeper look. Next step: reconcile SoftDent to QuickBooks.",
        )
        self.assertTrue(score["hasCotLeak"])
        self.assertFalse(score["qualityPass"])

    def test_fee_grounding_pass(self) -> None:
        score = score_answer(
            "What is the allowed amount for D2740 on Delta Dental?",
            "Delta Dental schedule lists D2740 at $845. Cite the fee schedule; verify on the EOB.",
        )
        self.assertTrue(score["groundingApplicable"])
        self.assertTrue(score["grounded"])
        self.assertTrue(score["qualityPass"])

    def test_fee_grounding_fail_invented(self) -> None:
        score = score_answer(
            "What is the allowed amount for D2740 on Delta Dental?",
            "Delta Dental usually allows about $700 for a crown. Staff should verify.",
        )
        self.assertTrue(score["groundingApplicable"])
        self.assertFalse(score["grounded"])
        self.assertFalse(score["qualityPass"])

    def test_payer_phone_grounding(self) -> None:
        score = score_answer(
            "What is MetLife eligibility phone?",
            "MetLife eligibility phone is (800) 638-5433. Staff should verify on the card before calling.",
        )
        self.assertTrue(score["grounded"])
        self.assertTrue(score["qualityPass"])

    def test_expanded_fee_and_phone_gold(self) -> None:
        fee = score_answer(
            "What is allowed for D1110 on Delta Dental?",
            "Delta Dental schedule lists D1110 at $68. Cite the fee schedule export.",
        )
        self.assertTrue(fee["grounded"])
        phone = score_answer(
            "What is Humana eligibility phone?",
            "Humana eligibility phone is (800) 833-2223. Staff should verify on the card.",
        )
        self.assertTrue(phone["grounded"])

    def test_generic_insurance_honesty(self) -> None:
        score = score_answer(
            "Which payer is on the claim labeled generic Insurance?",
            "The claim only says Insurance — carrier join is unavailable from daysheet; verify SoftDent InsCo export.",
        )
        self.assertTrue(score["groundingApplicable"])
        self.assertTrue(score["grounded"])


if __name__ == "__main__":
    unittest.main()
