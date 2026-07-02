"""Tests for per-dataset checksum change detection in import diagnostics."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from import_diagnostics import STATUS_CONNECTED, STATUS_PARTIAL, evaluate_dataset


class ImportDiagnosticsChecksumTests(unittest.TestCase):
    def test_checksum_change_downgrades_connected_to_partial(self) -> None:
        contract = {
            "system": "softdent",
            "bundleKey": "dashboard",
            "automated": True,
            "severity": "critical",
            "freshnessMaxMinutes": 1440,
            "requiredFields": ["production"],
            "fieldAliases": {"production": ["production"]},
        }
        payload = {
            "sourceFile": "softdent_dashboard_data.json",
            "modifiedAt": datetime.now(timezone.utc).isoformat(),
            "sha256": "bbbb",
            "rows": [
                {"production": 100, "period": "2026-06"},
                {"production": 90, "period": "2026-05"},
            ],
        }
        previous = {
            "softdent.dashboard": {
                "sourceFile": "softdent_dashboard_data.json",
                "sha256": "aaaa",
            }
        }
        item = evaluate_dataset(
            "softdent.dashboard",
            contract,
            payload,
            previous_checksums=previous,
        )
        self.assertEqual(item["status"], STATUS_PARTIAL)
        self.assertTrue(item["checksumChanged"])
        self.assertIn("checksum", item["detail"].lower())

    def test_matching_checksum_stays_connected(self) -> None:
        contract = {
            "system": "softdent",
            "bundleKey": "dashboard",
            "automated": True,
            "severity": "critical",
            "freshnessMaxMinutes": 1440,
            "requiredFields": ["production"],
            "fieldAliases": {"production": ["production"]},
        }
        payload = {
            "sourceFile": "softdent_dashboard_data.json",
            "modifiedAt": datetime.now(timezone.utc).isoformat(),
            "sha256": "same-hash",
            "rows": [
                {"production": 100, "period": "2026-06"},
                {"production": 90, "period": "2026-05"},
            ],
        }
        previous = {
            "softdent.dashboard": {
                "sourceFile": "softdent_dashboard_data.json",
                "sha256": "same-hash",
            }
        }
        item = evaluate_dataset(
            "softdent.dashboard",
            contract,
            payload,
            previous_checksums=previous,
        )
        self.assertEqual(item["status"], STATUS_CONNECTED)
        self.assertFalse(item["checksumChanged"])


if __name__ == "__main__":
    unittest.main()
