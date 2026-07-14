"""SoftDent full product knowledge base loader + HAL policy."""

from __future__ import annotations

import unittest

from softdent_product_kb import (
    clear_softdent_product_kb_cache,
    format_softdent_product_kb_hal_reply,
    load_softdent_product_kb,
    load_softdent_product_topic_bodies,
    lookup_report,
    lookup_topic_bodies,
    product_kb_summary,
    query_touches_softdent_product,
)


class SoftDentProductKbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        clear_softdent_product_kb_cache()

    def test_kb_loads_with_toc_reports_and_bodies(self):
        kb = load_softdent_product_kb()
        self.assertGreaterEqual(int((kb.get("helpToc") or {}).get("entryCount") or 0), 1000)
        self.assertGreaterEqual(int((kb.get("reportCatalog") or {}).get("reportCountParsed") or 0), 100)
        bodies = load_softdent_product_topic_bodies()
        self.assertGreaterEqual(len(bodies), 500)
        summary = product_kb_summary()
        self.assertIn("Accounting", summary.get("categoryCounts") or {})
        self.assertGreater((summary.get("categoryCounts") or {}).get("Accounting", 0), 5)
        self.assertGreaterEqual(int(summary.get("topicBodyCount") or 0), 500)
        how = kb.get("howSoftDentWorks") or {}
        self.assertTrue(how.get("summary"))
        self.assertGreaterEqual(len(how.get("lifecycle") or []), 5)
        self.assertGreaterEqual(len(how.get("coreHelpArticles") or {}), 3)

    def test_deep_body_lookup_and_hal_reply(self):
        hits = lookup_report("Account Aging", limit=5)
        self.assertTrue(hits)
        bodies = lookup_topic_bodies("Account Aging", limit=5)
        self.assertTrue(bodies)
        self.assertTrue(any("aging" in str(b.get("title") or "").lower() or "aging" in str(b.get("body") or "").lower() for b in bodies))
        text = format_softdent_product_kb_hal_reply("How does SoftDent Account Aging work?")
        self.assertIn("INSIDE-OUT", text)
        self.assertIn("Aging", text)
        self.assertIn("Help article text", text)

    def test_query_touch_and_local_policy(self):
        self.assertTrue(query_touches_softdent_product("Tell me about the SoftDent product modules"))
        self.assertTrue(query_touches_softdent_product("What SoftDent reports are in Practice Management?"))
        self.assertTrue(query_touches_softdent_product("Does HAL know SoftDent inside and out?"))
        from nr2_hal_gateway import try_local_policy_reply

        hit = try_local_policy_reply("Describe the SoftDent product Help catalog")
        self.assertIsNotNone(hit)
        self.assertEqual(hit.get("intent"), "policy:softdent-product-kb")
        self.assertIn("Help", hit.get("text") or "")

    def test_compile_guidance_includes_product_kb(self):
        from softdent_signon import compile_softdent_signon_guidance

        guided = compile_softdent_signon_guidance("What is SoftDent charting in the full product?")
        self.assertIn("INSIDE-OUT", guided)


if __name__ == "__main__":
    unittest.main()
