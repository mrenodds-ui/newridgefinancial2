"""Moonshot DEF-001 Collections/Daysheet after Phase 5 (hal-10564 → period ingest hal-10576)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from apex_backend import BUILD_ID, resolve_hal_board_actions
from apex_financial_console_pack import build_revenue_composition
from apex_softdent_hardening_pack import (
    GAP_COLLECTIONS_PENDING,
    GAP_DAYSHEET_WITHOUT_SPLIT,
    GAP_NO_PERIOD,
    assess_collections_gap,
    collections_gap_widget,
    format_collections_gap_reply,
    scan_collections_export_inbox,
)
from nr2_hal_gateway import try_local_policy_reply
from softdent_dashboard_period_sync import ingest_daysheet_to_period
from softdent_practice_exports import detect_daysheet_export_schema, summarize_daysheet_export

# ERA enrich may upgrade pending → ERA_835_AVAILABLE when live 835s exist
_PENDING_CODES = {
    GAP_COLLECTIONS_PENDING,
    "ERA_835_AVAILABLE",
    "COLLECTIONS_FORMAT_REQUIRED",
    "DAYSHEET_WITHOUT_SPLIT",
    "COLLECTIONS_EXPORT_REQUIRED",
}


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
        },
        "diagnostics": {"summary": {"connected": 3, "total": 5, "missing": 2}},
        "loadedAt": "2026-07-12T12:00:00Z",
    }


class CollectionsDaysheetHal10564Tests(unittest.TestCase):
    def test_build_id(self):
        self.assertEqual(BUILD_ID, "hal-10576")

    def test_inbox_scan_finds_collections_named_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Collections_202607.csv").write_text("a,b\n1,2\n", encoding="utf-8")
            with mock.patch.dict(
                "os.environ",
                {"SOFTDENT_REPORT_EXPORTS": str(root), "NR2_SOFTDENT_EXPORT_SOURCE": ""},
                clear=False,
            ):
                inbox = scan_collections_export_inbox(limit=8)
            self.assertGreaterEqual(inbox.get("matchCount") or 0, 1)
            self.assertTrue(inbox.get("hasCollectionsLikeFile"))
            self.assertTrue(any(m.get("name") == "Collections_202607.csv" for m in inbox.get("matches") or []))

    def test_gap_includes_export_inbox(self):
        gap = assess_collections_gap(_bundle_pending())
        self.assertIn(gap.get("gapCode"), _PENDING_CODES)
        self.assertFalse(gap.get("healthy"))
        self.assertIn("exportInbox", gap)
        self.assertIsNone(gap.get("collections"))
        text = format_collections_gap_reply(gap)
        self.assertIn("DEF-001", text)
        self.assertIn("SoftDentReportExports", text)
        self.assertIn("Export inbox:", text)

    def test_revenue_composition_period_aware_empty(self):
        w = build_revenue_composition(_bundle_pending())
        self.assertEqual(w.get("status"), "empty")
        self.assertIn(w.get("gapCode"), _PENDING_CODES)
        msg = str(w.get("emptyMessage") or "")
        self.assertIn("2026-07", msg)
        self.assertRegex(msg.lower().replace("≠", "not "), r"empty|pending|gap|split")
        self.assertIn("SoftDentReportExports", msg)

    def test_financial_gap_strip_contract(self):
        rev = build_revenue_composition(_bundle_pending())
        gap_w = collections_gap_widget(_bundle_pending())
        self.assertEqual(rev.get("status"), "empty")
        self.assertEqual(gap_w.get("status"), "empty")
        self.assertEqual(gap_w.get("id"), "softdent-collections-gap")
        self.assertEqual(rev.get("def"), "DEF-001")

    def test_hal_board_revenue_composition_empty(self):
        with mock.patch(
            "apex_backend._load_reports_and_bundle",
            return_value=({}, _bundle_pending(), None),
        ):
            r = resolve_hal_board_actions(
                {"query": "why is revenue composition empty?", "page": "hal"}
            )
        self.assertTrue(r.get("handled"))
        reply = str(r.get("reply") or "")
        self.assertIn("DEF-001", reply)
        actions = r.get("actions") or []
        self.assertTrue(any(a.get("widgetId") == "revenue-composition" for a in actions))

    def test_local_policy_def001(self):
        with mock.patch(
            "apex_backend._load_reports_and_bundle",
            return_value=({}, _bundle_pending(), None),
        ):
            hit = try_local_policy_reply("Why is revenue composition empty?")
        self.assertIsNotNone(hit)
        self.assertEqual(hit.get("intent"), "policy:def-001-collections")
        self.assertIn("DEF-001", hit.get("text") or "")

    def test_daysheet_schema_and_period_stub_from_inbox(self):
        """Files present / period null → period created (no invented $0 split)."""
        sample = (
            "Daysheet,,,,,,,,,,,,,,\n"
            "For Practice,,,,,,,,,,,,,,\n"
            '"May 28, 2026",,,,,,,,,,,,,,\n'
            ",,,,,,,,,,,,,,\n"
            ",ID,Name,D$,Dr,Code,Description,Prod,Charges,Prod Adj,Cash,Check,Credit,Pay. Adj,Transaction Notes\n"
            ' ,1,"A, B",1,1,1110,Prophylaxis - Adult,$100.00,,,,,,,\n'
            ' ,1,"A, B",1,,2,Insurance Check Payment,,,,,$50.00,,,\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            daysheet = root / "daysheet.csv"
            daysheet.write_text(sample, encoding="utf-8")
            schema = detect_daysheet_export_schema(daysheet)
            self.assertEqual(schema.get("kind"), "daysheet_csv")
            self.assertIn("2026-05", schema.get("periodHints") or [])
            summary = summarize_daysheet_export(daysheet)
            self.assertIsNotNone(summary)
            self.assertEqual(summary.get("period"), "2026-05")
            self.assertGreater(float(summary.get("production") or 0), 0)
            self.assertTrue(summary.get("daysheetWithoutSplit"))
            self.assertFalse(summary.get("hasInsurancePatientSplit"))

            dest = root / "softdent_out"
            dest.mkdir()
            with mock.patch.dict(
                "os.environ",
                {"SOFTDENT_REPORT_EXPORTS": str(root), "NR2_SOFTDENT_EXPORT_SOURCE": ""},
                clear=False,
            ):
                with mock.patch(
                    "softdent_dashboard_period_sync.softdent_import_dir",
                    return_value=dest,
                ):
                    with mock.patch(
                        "softdent_dashboard_period_sync.relevant_period_labels",
                        return_value=["2026-07", "2026-06"],
                    ):
                        result = ingest_daysheet_to_period(force_reimport=True)
            self.assertTrue(result.get("ok"))
            self.assertIn("2026-05", result.get("created") or [])
            dash_path = dest / "softdent_dashboard_data.json"
            self.assertTrue(dash_path.is_file())
            rows = json.loads(dash_path.read_text(encoding="utf-8"))
            may = next(r for r in rows if r.get("period") == "2026-05")
            self.assertGreater(float(may.get("production") or 0), 0)
            self.assertTrue(may.get("collectionsPending") or may.get("daysheetWithoutSplit"))
            self.assertEqual(float(may.get("insurance") or 0), 0.0)
            self.assertEqual(float(may.get("patient") or 0), 0.0)
            # After stub exists, gap must not be NO_PERIOD_ROW
            gap = assess_collections_gap(
                {"softdent": {"dashboard": {"rows": rows}}, "loadedAt": "2026-07-12T12:00:00Z"}
            )
            self.assertIsNotNone(gap.get("period"))
            self.assertNotEqual(gap.get("gapCode"), GAP_NO_PERIOD)

    def test_daysheet_without_split_gap_code(self):
        with mock.patch(
            "apex_softdent_hardening_pack.scan_collections_export_inbox",
            return_value={
                "ok": True,
                "matchCount": 1,
                "hasCollectionsLikeFile": False,
                "hasDaysheetLikeFile": True,
                "hasRegisterLikeFile": False,
                "matches": [{"name": "daysheet.csv", "path": "C:/tmp/daysheet.csv", "kind": "daysheet"}],
                "hint": "files",
                "roots": ["C:/tmp"],
            },
        ):
            with mock.patch(
                "apex_softdent_hardening_pack.classify_daysheet_inbox_periods",
                return_value={"periods": ["2026-07"], "notes": []},
            ):
                with mock.patch(
                    "apex_softdent_era_pack.enrich_collections_gap_with_era",
                    side_effect=lambda g, **kw: g,
                ):
                    gap = assess_collections_gap(
                        {
                            "softdent": {
                                "dashboard": {
                                    "rows": [
                                        {
                                            "period": "2026-07",
                                            "production": 10000,
                                            "collectionsPending": True,
                                            "daysheetWithoutSplit": True,
                                            "insurance": 0,
                                            "patient": 0,
                                        }
                                    ]
                                }
                            },
                            "loadedAt": "2026-07-12T12:00:00Z",
                        }
                    )
        self.assertEqual(gap.get("gapCode"), GAP_DAYSHEET_WITHOUT_SPLIT)
        self.assertTrue(gap.get("daysheetWithoutSplit"))
        self.assertTrue(gap.get("collectionsExportRequired"))
        self.assertEqual(gap.get("collectionsGapCode"), "COLLECTIONS_EXPORT_REQUIRED")
        self.assertIsNone(gap.get("collections"))
        text = format_collections_gap_reply(gap)
        self.assertIn("Collections export required", text)

    def test_register_with_ins_plan_split_populates(self):
        sample = (
            "Register for a Period\n"
            "For Practice New Ridge Family Dental\n"
            "July 1, 2026 through July 11, 2026\n"
            ",Productions,,$25000.00\n"
            ",Collections,,$18000.00\n"
            ",Ins Plan Collections,,$12000.00\n"
            ",Regular Collections,,$6000.00\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "register_for_period.csv"
            path.write_text(sample, encoding="utf-8")
            schema = detect_daysheet_export_schema(path)
            self.assertEqual(schema.get("kind"), "register_csv")
            self.assertTrue(schema.get("hasInsurancePatientSplit"))
            summary = summarize_daysheet_export(path)
            self.assertIsNotNone(summary)
            self.assertEqual(summary.get("period"), "2026-07")
            self.assertFalse(summary.get("daysheetWithoutSplit"))
            self.assertTrue(summary.get("hasInsurancePatientSplit"))
            self.assertEqual(float(summary.get("insurance") or 0), 12000.0)
            self.assertEqual(float(summary.get("patient") or 0), 6000.0)

            dest = Path(tmp) / "out"
            dest.mkdir()
            with mock.patch.dict(
                "os.environ",
                {"SOFTDENT_REPORT_EXPORTS": str(tmp), "NR2_SOFTDENT_EXPORT_SOURCE": ""},
                clear=False,
            ):
                with mock.patch(
                    "softdent_dashboard_period_sync.softdent_import_dir",
                    return_value=dest,
                ):
                    with mock.patch(
                        "softdent_dashboard_period_sync.relevant_period_labels",
                        return_value=["2026-07", "2026-06"],
                    ):
                        result = ingest_daysheet_to_period(force_reimport=True)
            self.assertTrue(result.get("ok"))
            self.assertIn("2026-07", result.get("created") or [])
            rows = json.loads((dest / "softdent_dashboard_data.json").read_text(encoding="utf-8"))
            jul = next(r for r in rows if r.get("period") == "2026-07")
            self.assertEqual(float(jul.get("insurance") or 0), 12000.0)
            self.assertEqual(float(jul.get("patient") or 0), 6000.0)
            self.assertTrue(jul.get("collectionsReported"))
            self.assertNotIn("collectionsPending", jul)


if __name__ == "__main__":
    unittest.main()
