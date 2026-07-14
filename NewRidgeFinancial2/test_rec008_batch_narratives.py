"""REC-008 batch narrative generation tests."""

from __future__ import annotations

import unittest
from unittest import mock


class BatchNarrativeSeedTests(unittest.TestCase):
    def test_seed_requires_ids(self) -> None:
        from apex_program_improve_pack import batch_narrative_seed

        self.assertFalse(batch_narrative_seed([])["ok"])

    def test_seed_caps_batch(self) -> None:
        from apex_program_improve_pack import BATCH_NARRATIVE_MAX, batch_narrative_seed

        ids = [f"c{i}" for i in range(BATCH_NARRATIVE_MAX + 1)]
        out = batch_narrative_seed(ids)
        self.assertFalse(out["ok"])

    def test_seed_ok(self) -> None:
        from apex_program_improve_pack import batch_narrative_seed

        out = batch_narrative_seed(["A1", "B2"], payer="Delta")
        self.assertTrue(out["ok"])
        self.assertEqual(out["seed"]["claimIds"], ["A1", "B2"])
        self.assertTrue(out["seed"]["batchNarrative"])


class BatchNarrativeGenerateTests(unittest.TestCase):
    def test_consent_required(self) -> None:
        from apex_backend import narrative_batch_generate

        out = narrative_batch_generate({"claimIds": ["c1"]})
        self.assertFalse(out["ok"])
        self.assertIn("consent", (out.get("error") or "").lower())

    @mock.patch("apex_backend.narrative_print_packet")
    @mock.patch("apex_backend.narrative_insurance_generate")
    @mock.patch("apex_program_improve_pack.record_claim_action")
    def test_batch_loops_and_builds_packet(
        self, _mock_action: mock.MagicMock, mock_gen: mock.MagicMock, mock_pkt: mock.MagicMock
    ) -> None:
        from apex_backend import narrative_batch_generate

        mock_gen.side_effect = [
            {"ok": True, "draftText": "Draft for c1", "sourcesCited": ["claim:c1"]},
            {"ok": False, "error": "Claim not found in SoftDent import."},
        ]
        mock_pkt.return_value = {"ok": True, "url": "/api/apex/narratives/packet/job1", "jobId": "job1"}
        out = narrative_batch_generate(
            {"claimIds": ["c1", "c2"], "operatorConsent": True, "type": "appeal", "denialReason": "CO-45"}
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["successCount"], 1)
        self.assertEqual(out["failCount"], 1)
        self.assertEqual(mock_gen.call_count, 2)
        self.assertTrue(mock_pkt.called)
        sections = mock_pkt.call_args[0][0]["sections"]
        self.assertEqual(len(sections), 1)
        self.assertIn("c1", sections[0]["title"])


if __name__ == "__main__":
    unittest.main()
