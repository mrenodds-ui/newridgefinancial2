"""Moonshot UI mutation-token wiring for ERA inbox ingest (hal-10576)."""

from __future__ import annotations

import unittest

from apex_backend import BUILD_ID
from apex_era835_pack import era_inbox_status, ingest_era_inbox
from apex_softdent_hardening_pack import (
    GAP_ERA_835_REQUIRED,
    assess_collections_gap,
    collections_gap_widget,
)
from nr2_browser_security import (
    ERA_INBOX_INGEST_URL,
    MUTATION_HEADER,
    era_inbox_mutation_contract,
)
from nr2_hal_gateway import try_local_policy_reply


def _bundle_register_ins_plan_zero() -> dict:
    return {
        "softdent": {
            "dashboard": {
                "rows": [
                    {
                        "period": "2026-07",
                        "year_month": "2026-07",
                        "production": 44735.0,
                        "collections": 30626.42,
                        "collectionsReported": True,
                        "collectionsPending": False,
                        "collectionsFormatRequired": True,
                        "insurance": 0.0,
                        "patient": 0.0,
                        "insPlanCollections": 0.0,
                        "sourceKind": "register",
                    }
                ]
            }
        }
    }


class Hal10574MutationTokenEraInboxTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10576")

    def test_mutation_contract_shape(self) -> None:
        c = era_inbox_mutation_contract()
        self.assertTrue(c.get("mutationAuthRequired"))
        self.assertEqual(c.get("mutationHeader"), MUTATION_HEADER)
        self.assertEqual(c.get("ingestUrl"), ERA_INBOX_INGEST_URL)
        self.assertEqual(c.get("ingestMethod"), "POST")
        self.assertEqual(c.get("mutationAcquireVia"), "/api/app-info")
        self.assertIn("run_era_inbox_ingest_ops.py", str(c.get("cliFallback") or ""))
        self.assertNotIn("mutationToken", c)

    def test_mutation_contract_with_token(self) -> None:
        c = era_inbox_mutation_contract(mutation_token="tok-abc")
        self.assertEqual(c.get("mutationToken"), "tok-abc")
        self.assertEqual(c.get("sessionToken"), "tok-abc")

    def test_era_inbox_status_exposes_contract(self) -> None:
        st = era_inbox_status(ensure_dirs=True)
        self.assertTrue(st.get("ok"))
        self.assertTrue(st.get("mutationAuthRequired"))
        self.assertEqual(st.get("mutationHeader"), "X-NR2-Session-Token")
        self.assertEqual(st.get("ingestUrl"), "/api/apex/hal/era-inbox/ingest")
        self.assertTrue(st.get("empty"))
        self.assertEqual(st.get("honesty"), "empty_not_zero")
        self.assertFalse(st.get("writeBack"))

    def test_gap_widget_exposes_refresh_inbox_action(self) -> None:
        gap = assess_collections_gap(_bundle_register_ins_plan_zero())
        self.assertEqual(gap.get("collectionsGapCode"), GAP_ERA_835_REQUIRED)
        w = collections_gap_widget(_bundle_register_ins_plan_zero())
        self.assertEqual(w.get("eraInboxIngestUrl"), "/api/apex/hal/era-inbox/ingest")
        self.assertEqual(w.get("eraInboxIngestLabel"), "Refresh Inbox")

    def test_empty_ingest_honesty(self) -> None:
        result = ingest_era_inbox(ensure_dirs=True)
        self.assertTrue(result.get("ok"))
        self.assertTrue(result.get("empty"))
        self.assertEqual(result.get("honesty"), "empty_not_zero")
        self.assertFalse(result.get("writeBack"))
        self.assertEqual(result.get("ingested") or [], [])

    def test_hal_policy_refresh_inbox(self) -> None:
        reply = try_local_policy_reply("refresh era inbox")
        self.assertIsNotNone(reply)
        assert reply is not None
        self.assertEqual(reply.get("intent"), "policy:era-inbox-refresh")
        self.assertIn("Refresh Inbox", reply.get("text") or "")
        self.assertIn("empty ≠ $0", reply.get("text") or "")


if __name__ == "__main__":
    unittest.main()
