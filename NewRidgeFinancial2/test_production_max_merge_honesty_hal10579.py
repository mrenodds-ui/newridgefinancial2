"""July production max-merge honesty — Register beats provider_prod (hal-10579)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from softdent_dashboard_period_sync import (
    _build_period_row,
    _merge_production,
    ingest_daysheet_to_period,
    sync_dashboard_period_rows,
)


class ProductionMaxMergeHonestyHal10579Tests(unittest.TestCase):
    def test_production_max_merge_honesty_hal10579(self) -> None:
        # provider_prod alone would inflate; Register/daysheet authority must win.
        sources = [
            {
                "_source": "daysheet",
                "productionAuthority": "softdent_period",
                "production": 44735.0,
                "collections": 30626.42,
                "collectionsReported": True,
                "insurance": 0.0,
                "patient": 0.0,
            },
            {"_source": "provider_prod", "production": 45684.25},
            {
                "_source": "bridge",
                "productionAuthority": "softdent_period",
                "production": 44735.0,
                "collections": 30626.0,
                "insurance": 0.0,
                "patient": 30626.0,
            },
        ]
        self.assertEqual(_merge_production(sources), 44735.0)
        row = _build_period_row("2026-07", sources)
        self.assertAlmostEqual(float(row.get("production") or 0), 44735.0, places=2)
        self.assertEqual(row.get("productionAuthority"), "register")

        register_inbox = {
            "_source": "inbox_export",
            "sourceKind": "register_xls",
            "productionAuthority": "register",
            "production": 44735.0,
            "collections": 30626.42,
            "collectionsReported": True,
            "insurance": 0.0,
            "patient": 30626.42,
            "regularCollections": 30626.42,
            "regularCollectionsReported": True,
            "registerInsPlanZero": True,
            "insuranceSplitReported": True,
        }
        inflated = _build_period_row(
            "2026-07",
            [register_inbox, {"_source": "provider_prod", "production": 45684.25}],
        )
        self.assertAlmostEqual(float(inflated.get("production") or 0), 44735.0, places=2)
        self.assertAlmostEqual(float(inflated.get("patient") or 0), 30626.42, places=2)
        self.assertTrue(inflated.get("registerInsPlanZero"))

    def test_sync_keeps_register_production_over_provider_prod(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "softdent"
            dest.mkdir()
            prior = [
                {
                    "provider": "New Ridge Family Dental",
                    "period": "2026-07",
                    "production": 44735.0,
                    "collections": 30626.42,
                    "collectionsReported": True,
                    "insurance": 0.0,
                    "patient": 30626.42,
                    "regularCollections": 30626.42,
                    "regularCollectionsReported": True,
                    "registerInsPlanZero": True,
                    "productionAuthority": "register",
                    "insuranceSplitReported": True,
                }
            ]
            (dest / "softdent_dashboard_data.json").write_text(
                json.dumps(prior, indent=2), encoding="utf-8"
            )
            generated = [
                {
                    "provider": "New Ridge Family Dental",
                    "period": "2026-07",
                    "production": 45684.25,
                    "insurance": 0.0,
                    "patient": 0.0,
                    "collections": 30626.42,
                    "collectionsReported": True,
                    "collectionsFormatRequired": True,
                }
            ]
            with mock.patch(
                "softdent_dashboard_period_sync.softdent_import_dir",
                return_value=dest,
            ):
                with mock.patch(
                    "softdent_dashboard_period_sync.ingest_daysheet_to_period",
                    return_value={"ok": True, "created": [], "updated": []},
                ):
                    with mock.patch(
                        "softdent_dashboard_period_sync.relevant_period_labels",
                        return_value=["2026-07"],
                    ):
                        with mock.patch(
                            "softdent_dashboard_period_sync.resolve_analytics_db",
                            return_value=None,
                        ):
                            with mock.patch(
                                "softdent_dashboard_period_sync._month_rows",
                                return_value=generated,
                            ):
                                with mock.patch(
                                    "softdent_dashboard_period_sync.diagnose_collections_gap",
                                    return_value={"issues": []},
                                ):
                                    result = sync_dashboard_period_rows(force_reimport=False)
            self.assertTrue(result.get("ok"))
            rows = json.loads((dest / "softdent_dashboard_data.json").read_text(encoding="utf-8"))
            jul = next(r for r in rows if r.get("period") == "2026-07")
            self.assertAlmostEqual(float(jul.get("production") or 0), 44735.0, places=2)
            self.assertAlmostEqual(float(jul.get("patient") or 0), 30626.42, places=2)
            self.assertTrue(jul.get("registerInsPlanZero"))


if __name__ == "__main__":
    unittest.main()
