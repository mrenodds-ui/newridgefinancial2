"""Payer reference + eligibility cache stores."""

from __future__ import annotations

import unittest

from eligibility_cache_store import (
    format_eligibility_hits,
    list_eligibility_entries,
    normalize_eligibility_entry,
    search_eligibility_cache,
    upsert_eligibility_entry,
)
from payer_reference_store import enrich_claim_payer, format_claim_payer_joins, format_payer_hits, search_payers


class PayerReferenceTests(unittest.TestCase):
    def test_search_delta_dental(self) -> None:
        hits = search_payers("Delta Dental crown denial code 16", limit=2)
        self.assertTrue(hits)
        self.assertIn("delta", str(hits[0].get("id") or "").lower())

    def test_format_payer_hits_includes_disclaimer(self) -> None:
        hits = search_payers("MetLife", limit=1)
        text = format_payer_hits(hits)
        self.assertIn("Payer reference matches", text)
        self.assertIn("not member-specific", text.lower())

    def test_format_payer_hits_includes_eligibility_contacts(self) -> None:
        hits = search_payers("MetLife eligibility phone", limit=1)
        self.assertTrue(hits)
        text = format_payer_hits(hits)
        self.assertIn("Eligibility / claim contacts", text)
        self.assertRegex(text, r"\(800\)\s*638-5433")

    def test_enrich_claim_payer_joins_metlife(self) -> None:
        match = enrich_claim_payer("METLIFE DENTAL")
        self.assertIsNotNone(match)
        assert match is not None
        self.assertIn("metlife", str(match.get("matchedName") or "").lower())
        self.assertTrue(match.get("tesiaPayerId"))
        self.assertIsNone(enrich_claim_payer("Insurance"))
        text = format_claim_payer_joins(
            [{"id": "C1", "payer": "METLIFE DENTAL", "status": "Denied"}, {"id": "C2", "payer": "Insurance"}]
        )
        self.assertIn("Claim <-> payer reference", text)
        self.assertIn("METLIFE", text.upper())
        self.assertRegex(text, r"Tesia/Vyne\s+(0000E|65978)")


class EligibilityCacheTests(unittest.TestCase):
    def test_normalize_requires_payer_name(self) -> None:
        with self.assertRaises(ValueError):
            normalize_eligibility_entry({})

    def test_upsert_and_search(self) -> None:
        result = upsert_eligibility_entry(
            {
                "payerName": "Test Payer NR2",
                "payerId": "TEST1",
                "source": "unit_test",
                "annualMaxRemaining": 900,
                "deductibleRemaining": 25,
                "ttlHours": 72,
            }
        )
        self.assertTrue(result.get("ok"))
        hits = search_eligibility_cache("Test Payer NR2", limit=2)
        self.assertTrue(hits)
        text = format_eligibility_hits(hits)
        self.assertIn("Cached eligibility context", text)
        fresh = list_eligibility_entries(limit=50, fresh_only=True)
        self.assertTrue(any(str(row.get("payerName") or "") == "Test Payer NR2" for row in fresh))

    def test_search_does_not_fallback_unrelated(self) -> None:
        upsert_eligibility_entry(
            {
                "payerName": "Unrelated Fallback Payer",
                "payerId": "FALL1",
                "source": "unit_test",
                "annualMaxRemaining": 100,
                "ttlHours": 72,
            }
        )
        hits = search_eligibility_cache("zzqx ymloff qorbex nonsense tokens", limit=2)
        self.assertEqual(hits, [])

    def test_query_wants_eligibility(self) -> None:
        from eligibility_cache_store import query_wants_eligibility

        self.assertTrue(query_wants_eligibility("What is the deductible remaining?"))
        self.assertTrue(query_wants_eligibility("run 270 eligibility for MetLife"))
        self.assertFalse(query_wants_eligibility("What is the allowed for D2740 on Delta?"))
        self.assertFalse(query_wants_eligibility("MetLife eligibility phone number"))


class GatewayPayerInjectionTests(unittest.TestCase):
    def test_build_chat_messages_injects_payer_reference(self) -> None:
        from nr2_hal_gateway import build_chat_messages

        messages, _, _, _ = build_chat_messages(
            query="MetLife denied crown D2740 code 16 narrative",
            readiness={"level": "fresh"},
        )
        payer_msgs = [m for m in messages if "Payer reference matches" in str(m.get("content") or "")]
        self.assertTrue(payer_msgs)
        contact_msgs = [m for m in messages if "Eligibility / claim contacts" in str(m.get("content") or "")]
        self.assertTrue(contact_msgs)

    def test_build_chat_messages_skips_eligibility_without_intent(self) -> None:
        from nr2_hal_gateway import build_chat_messages, compile_eligibility_context

        upsert_eligibility_entry(
            {
                "payerName": "Leak Test Payer",
                "source": "unit_test",
                "deductibleRemaining": 12,
                "ttlHours": 72,
            }
        )
        # Fee/CDT question must not pull unrelated eligibility cache
        self.assertEqual(compile_eligibility_context("allowed for D2740 on Delta", ""), "")
        messages, _, _, _ = build_chat_messages(
            query="allowed for D2740 on Delta",
            readiness={"level": "fresh"},
        )
        elig_msgs = [m for m in messages if "Cached eligibility context" in str(m.get("content") or "")]
        self.assertFalse(elig_msgs)


class FeeScheduleStoreTests(unittest.TestCase):
    def test_lookup_delta_d2740(self) -> None:
        from fee_schedule_store import format_fee_hits, lookup_fees

        hits = lookup_fees("allowed for D2740 on Delta Dental", limit=1)
        self.assertTrue(hits)
        self.assertTrue(hits[0].get("ok"))
        self.assertEqual(hits[0].get("code"), "D2740")
        amounts = hits[0].get("amounts") or []
        self.assertTrue(amounts)
        self.assertTrue(any("delta" in str(a.get("scheduleName") or "").lower() for a in amounts))
        text = format_fee_hits(hits)
        self.assertIn("Fee schedule matches", text)
        self.assertIn("845", text.replace(",", ""))

    def test_build_chat_messages_injects_fee_schedule(self) -> None:
        from nr2_hal_gateway import build_chat_messages

        messages, _, _, _ = build_chat_messages(
            query="What is the allowed amount for D2740 on Delta?",
            readiness={"level": "fresh"},
        )
        fee_msgs = [m for m in messages if "Fee schedule matches" in str(m.get("content") or "")]
        self.assertTrue(fee_msgs)


if __name__ == "__main__":
    unittest.main()
