"""Moonshot DEF-001 period sync honesty — COLLECTIONS_FORMAT_REQUIRED (hal-10576)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from apex_backend import BUILD_ID
from nr2_contracts.softdent_hardening import (
    GAP_COLLECTIONS_FORMAT_REQUIRED,
    GAP_COLLECTIONS_PENDING,
    assess_collections_gap,
    classify_daysheet_inbox_periods,
    format_collections_gap_reply,
)
from softdent_dashboard_period_sync import _build_period_row


_PENDING_OR_FORMAT = {GAP_COLLECTIONS_PENDING, GAP_COLLECTIONS_FORMAT_REQUIRED, "ERA_835_AVAILABLE"}


def _bundle_pending() -> dict:
    return {
        "softdent": {
            "dashboard": {
                "rows": [
                    {
                        "period": "2026-07",
                        "production": 50000,
                        "collectionsPending": True,
                        "insurance": 0,
                        "patient": 0,
                    }
                ]
            }
        }
    }


class PeriodSyncFormatHal10565Tests(unittest.TestCase):
    def test_build_id(self):
        self.assertEqual(BUILD_ID, "hal-10576")

    def test_classify_daysheet_may_period(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "daysheet.csv"
            path.write_text(
                "DaySheet for May 28, 2026\nID,Name,Prod\n1,A,10\n",
                encoding="utf-8",
            )
            classified = classify_daysheet_inbox_periods(
                [{"name": path.name, "path": str(path), "kind": "daysheet"}]
            )
        self.assertIn("2026-05", classified.get("periods") or [])

    def test_gap_format_required_when_inbox_wrong_period(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "daysheet.csv"
            path.write_text(
                "DaySheet for May 28, 2026\nID,Name,Prod\n1,A,10\n",
                encoding="utf-8",
            )
            with mock.patch(
                "nr2_contracts.softdent_hardening.scan_collections_export_inbox",
                return_value={
                    "ok": True,
                    "matchCount": 1,
                    "hasCollectionsLikeFile": False,
                    "hasDaysheetLikeFile": True,
                    "hasRegisterLikeFile": False,
                    "matches": [{"name": "daysheet.csv", "path": str(path), "kind": "daysheet"}],
                    "hint": "files",
                    "roots": [tmp],
                },
            ):
                with mock.patch(
                    "nr2_contracts.softdent_era.enrich_collections_gap_with_era",
                    side_effect=lambda g, **kw: g,
                ):
                    gap = assess_collections_gap(_bundle_pending())
        self.assertEqual(gap.get("gapCode"), GAP_COLLECTIONS_FORMAT_REQUIRED)
        self.assertTrue(gap.get("collectionsFormatRequired"))
        self.assertFalse((gap.get("exportInbox") or {}).get("coversOpenMonth"))
        text = format_collections_gap_reply(gap)
        self.assertIn("COLLECTIONS_FORMAT_REQUIRED", text)
        self.assertIn("Classified file periods", text)

    def test_no_invented_patient_from_zero_insurance(self):
        row = _build_period_row(
            "2026-06",
            [
                {
                    "_source": "daysheet",
                    "production": 100000.0,
                    "collections": 50000.0,
                    "insurance": 0.0,
                    "patient": 0.0,
                    "insuranceSplitReported": False,
                }
            ],
        )
        self.assertEqual(row.get("collections"), 50000.0)
        self.assertEqual(row.get("patient"), 0.0)
        self.assertTrue(row.get("collectionsFormatRequired"))


if __name__ == "__main__":
    unittest.main()
