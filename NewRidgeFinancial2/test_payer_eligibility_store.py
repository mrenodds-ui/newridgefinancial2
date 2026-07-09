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
from payer_reference_store import format_payer_hits, search_payers


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
        fresh = list_eligibility_entries(limit=5, fresh_only=True)
        self.assertTrue(any(str(row.get("payerName") or "") == "Test Payer NR2" for row in fresh))


class GatewayPayerInjectionTests(unittest.TestCase):
    def test_build_chat_messages_injects_payer_reference(self) -> None:
        from nr2_hal_gateway import build_chat_messages

        messages, _, _, _ = build_chat_messages(
            query="MetLife denied crown D2740 code 16 narrative",
            readiness={"level": "fresh"},
        )
        payer_msgs = [m for m in messages if "Payer reference matches" in str(m.get("content") or "")]
        self.assertTrue(payer_msgs)


if __name__ == "__main__":
    unittest.main()
