"""Phase S1 validation — ERA aggregates + collections gap enrich (no Ollama)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apex_softdent_era_pack import (
    GAP_ERA_835_AVAILABLE,
    enrich_collections_gap_with_era,
    record_era_aggregate,
)
from apex_softdent_hardening_pack import assess_collections_gap


class EraHardenPhaseS1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self._tmpdir.name) / "nr2_unified_s1.db"

    def tearDown(self) -> None:
        try:
            self._tmpdir.cleanup()
        except Exception:
            pass

    def test_record_aggregate(self):
        got = record_era_aggregate(
            payment_total=1500.0,
            claim_count=3,
            period="2026-07",
            source_file="sample.835",
            db_path=self.db_path,
        )
        self.assertTrue(got.get("ok"))
        self.assertEqual(got.get("period"), "2026-07")

    def test_enrich_pending_with_era(self):
        record_era_aggregate(
            payment_total=2200.0,
            claim_count=4,
            period="2026-07",
            db_path=self.db_path,
        )
        gap = {
            "gapCode": "COLLECTIONS_PENDING",
            "period": "2026-07",
            "healthy": False,
            "collections": None,
            "issues": ["pending"],
        }
        enriched = enrich_collections_gap_with_era(gap, db_path=self.db_path)
        self.assertEqual(enriched.get("gapCode"), GAP_ERA_835_AVAILABLE)
        self.assertTrue(enriched.get("eraAvailable"))
        self.assertIsNone(enriched.get("collections"))  # never invent SoftDent $
        self.assertIn("ERA", str(enriched.get("fixHint") or ""))

    def test_assess_still_honest_without_era(self):
        gap = assess_collections_gap(
            {
                "softdent": {
                    "dashboard": {
                        "rows": [
                            {
                                "period": "2026-07",
                                "production": 10000,
                                "collectionsPending": True,
                            }
                        ]
                    }
                }
            }
        )
        self.assertIn(gap.get("gapCode"), ("COLLECTIONS_PENDING", GAP_ERA_835_AVAILABLE))
        self.assertIsNone(gap.get("collections"))


if __name__ == "__main__":
    unittest.main()
