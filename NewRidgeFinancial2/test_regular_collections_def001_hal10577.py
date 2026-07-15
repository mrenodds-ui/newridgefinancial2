"""DEF-001 Regular Collections from July Register (Ins Plan $0 truth → ERA)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from nr2_contracts.softdent_hardening import (
    assess_collections_gap,
    collections_gap_widget,
)
from softdent_dashboard_period_sync import ingest_daysheet_to_period
from softdent_practice_exports import parse_softdent_register_xls

LIVE_REG = Path(r"C:\SoftDentReportExports\REG202607.XLS")


def _write_register_xlsx(path: Path, *, period_line: str, ins_plan: float, regular: float) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Register for a Period Report"
    ws.append(["Register for a Period"])
    ws.append([])
    ws.append([period_line])
    ws.append([])
    ws.append(["PRACTICE"])
    ws.append([])
    ws.append(["Productions", None, 25000.0])
    ws.append(["Collections", None, ins_plan + regular])
    ws.append([None, "Ins Plan Collections", None, ins_plan])
    ws.append([None, "Regular Collections", None, regular])
    wb.save(path)


class RegularCollectionsDef001Tests(unittest.TestCase):
    def test_parse_regular_when_ins_plan_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "REG202607.xlsx"
            _write_register_xlsx(
                path,
                period_line="07/01/26 thru 07/12/26",
                ins_plan=0.0,
                regular=30626.42,
            )
            summary = parse_softdent_register_xls(path)
            self.assertIsNotNone(summary)
            assert summary is not None
            self.assertEqual(float(summary["insurance"]), 0.0)
            self.assertEqual(float(summary.get("patient") or 0), 30626.42)
            self.assertEqual(float(summary.get("regularCollections") or 0), 30626.42)
            self.assertTrue(summary.get("regularCollectionsReported"))
            self.assertTrue(summary.get("registerInsPlanZero"))
            self.assertFalse(summary.get("collectionsFormatRequired"))

    def test_gap_widget_distinguishes_regular_vs_era(self) -> None:
        bundle = {
            "softdent": {
                "dashboard": {
                    "rows": [
                        {
                            "period": "2026-07",
                            "production": 44735.0,
                            "collections": 30626.42,
                            "collectionsReported": True,
                            "insurance": 0.0,
                            "patient": 30626.42,
                            "regularCollections": 30626.42,
                            "insPlanCollections": 0.0,
                            "regularCollectionsReported": True,
                            "registerInsPlanZero": True,
                            "insuranceSplitReported": True,
                        }
                    ]
                }
            }
        }
        gap = assess_collections_gap(bundle)
        self.assertTrue(gap.get("registerInsPlanZero"))
        self.assertEqual(gap.get("collectionsGapCode"), "ERA_835_REQUIRED")
        self.assertEqual(float(gap.get("patient") or 0), 30626.42)
        self.assertEqual(float(gap.get("regularCollections") or 0), 30626.42)
        self.assertEqual(float(gap["insurance"]), 0.0)
        self.assertFalse(gap.get("healthy"))
        w = collections_gap_widget(bundle)
        msg = w.get("message") or ""
        self.assertIn("Regular Collections: Complete", msg)
        self.assertIn("30626.42", msg.replace(",", ""))
        self.assertIn("ERA Required", msg)

    @unittest.skipUnless(LIVE_REG.is_file(), "REG202607.XLS not present")
    def test_live_reg202607_parse(self) -> None:
        summary = parse_softdent_register_xls(LIVE_REG)
        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertEqual(summary.get("period"), "2026-07")
        self.assertEqual(float(summary["insurance"]), 0.0)
        self.assertAlmostEqual(float(summary.get("patient") or 0), 30626.42, places=2)
        self.assertTrue(summary.get("registerInsPlanZero"))

    @unittest.skipUnless(LIVE_REG.is_file(), "REG202607.XLS not present")
    def test_live_ingest_force_updates_july(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "import"
            dest.mkdir()
            root = LIVE_REG.parent
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
            self.assertTrue(result.get("ok"), msg=str(result))
            rows = json.loads((dest / "softdent_dashboard_data.json").read_text(encoding="utf-8"))
            jul = next(r for r in rows if r.get("period") == "2026-07")
            self.assertAlmostEqual(float(jul.get("patient") or 0), 30626.42, places=2)
            self.assertEqual(float(jul["insurance"]), 0.0)
            self.assertTrue(jul.get("registerInsPlanZero") or jul.get("regularCollectionsReported"))


if __name__ == "__main__":
    unittest.main()
