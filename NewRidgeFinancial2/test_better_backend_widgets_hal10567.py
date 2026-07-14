"""Moonshot Better Backend Widgets MUST (hal-10576)."""

from __future__ import annotations

import unittest

from apex_backend import BUILD_ID
from apex_better_backend_widgets_pack import (
    build_collections_radial_gauge,
    build_system_health_status_matrix,
    build_tax_planning_data_table,
)


class BetterBackendWidgetsMustTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10576")

    def test_tax_planning_table_empty_honest(self) -> None:
        w = build_tax_planning_data_table({})
        self.assertIsNotNone(w)
        assert w is not None
        self.assertEqual(w["type"], "data-table")
        self.assertEqual(w["id"], "tax-planning-table")
        self.assertEqual(w["columns"], ["Item", "Type", "Status", "Impact", "Due"])
        self.assertIn(w["status"], {"empty", "ok"})

    def test_collections_gauge_empty_and_ok(self) -> None:
        empty = build_collections_radial_gauge({}, {})
        self.assertEqual(empty["type"], "radial-gauge")
        self.assertEqual(empty["status"], "empty")
        self.assertEqual(empty["data"]["mode"], "collections")
        self.assertEqual(empty["data"]["target"], 98)

        ok = build_collections_radial_gauge(
            {
                "softdent": {
                    "dashboard": {
                        "rows": [
                            {
                                "period": "2026-06",
                                "production": 100000,
                                "collections": 92000,
                            }
                        ]
                    }
                }
            },
            {},
        )
        self.assertEqual(ok["status"], "ok")
        self.assertEqual(ok["data"]["pctScheduled"], 92.0)
        self.assertEqual(ok["data"]["mode"], "collections")

    def test_system_health_matrix(self) -> None:
        w = build_system_health_status_matrix(
            {
                "diagnostics": {
                    "summary": {"connected": 2, "missing": 0, "stale": 1, "total": 4},
                    "datasets": [
                        {"key": "softdent_ar", "status": "connected"},
                        {"key": "quickbooks_pl", "status": "stale"},
                        {"key": "claims_feed", "status": "partial"},
                    ],
                }
            }
        )
        self.assertEqual(w["type"], "status-matrix")
        self.assertEqual(w["id"], "system-health-matrix")
        self.assertEqual(w["status"], "ok")
        self.assertEqual(w["data"]["headers"][0], "System")
        hashes = [p["hash"] for p in w["data"]["patients"]]
        self.assertEqual(hashes, ["SoftDent", "QuickBooks", "Claims", "HAL"])


if __name__ == "__main__":
    unittest.main()
