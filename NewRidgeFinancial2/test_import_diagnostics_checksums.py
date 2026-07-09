"""Tests for per-dataset checksum change detection in import diagnostics."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from import_diagnostics import STATUS_CONNECTED, STATUS_MISSING, STATUS_PARTIAL, evaluate_dataset


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

    def test_bridge_fallback_downgrades_dashboard_to_partial(self) -> None:
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
            "readSource": "bridge-fallback",
            "bridgeValidation": {"ok": True, "rowCount": 1, "issues": []},
            "rows": [{"production": 120000, "period": "2026-06", "collectionsReported": False}],
        }
        item = evaluate_dataset("softdent.dashboard", contract, payload)
        self.assertEqual(item["status"], STATUS_PARTIAL)
        self.assertIn("bridge fallback", item["detail"].lower())

    def test_operatory_chairs_payload_is_connected(self) -> None:
        contract = {
            "system": "softdent",
            "bundleKey": "operatory",
            "automated": True,
            "severity": "optional",
            "freshnessMaxMinutes": 1440,
            "requiredFields": ["operatoryChairs"],
        }
        payload = {
            "sourceFile": "operatory_schedule.json",
            "modifiedAt": datetime.now(timezone.utc).isoformat(),
            "sha256": "op-hash",
            "operatoryChairs": [
                {"name": "Room 1", "slots": [{"time": "07:00", "patient": "A", "procedure": "111000"}]},
                {"name": "Room 2", "slots": []},
            ],
            "rows": [],
        }
        item = evaluate_dataset("softdent.operatory", contract, payload)
        self.assertEqual(item["status"], STATUS_CONNECTED)
        self.assertEqual(item["rowCount"], 2)
        self.assertEqual(item["requiredFieldFailures"], [])

    def test_operatory_missing_chairs_is_missing(self) -> None:
        contract = {
            "system": "softdent",
            "bundleKey": "operatory",
            "automated": True,
            "severity": "optional",
            "freshnessMaxMinutes": 1440,
            "requiredFields": ["operatoryChairs"],
        }
        payload = {
            "sourceFile": "operatory_schedule.json",
            "modifiedAt": datetime.now(timezone.utc).isoformat(),
            "operatoryChairs": [],
            "rows": [],
        }
        item = evaluate_dataset("softdent.operatory", contract, payload)
        self.assertEqual(item["status"], STATUS_MISSING)
        self.assertEqual(item["requiredFieldFailures"], ["operatoryChairs"])


if __name__ == "__main__":
    unittest.main()
