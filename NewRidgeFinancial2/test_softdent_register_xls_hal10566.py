"""Moonshot DEF-001 Register XLS ingestion (hal-10576)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from apex_backend import BUILD_ID
from nr2_contracts.softdent_hardening import classify_daysheet_inbox_periods
from softdent_dashboard_period_sync import ingest_daysheet_to_period
from softdent_practice_exports import (
    detect_daysheet_export_schema,
    parse_softdent_register_xls,
    summarize_daysheet_export,
)


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


class SoftDentRegisterXlsHal10566Tests(unittest.TestCase):
    def test_build_id(self):
        self.assertEqual(BUILD_ID, "hal-10576")

    def test_parse_xlsx_with_ins_patient_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "RegisterForPeriodReportFor07122026.xlsx"
            _write_register_xlsx(
                path,
                period_line="07/01/26 thru 07/12/26",
                ins_plan=12000.0,
                regular=6000.0,
            )
            schema = detect_daysheet_export_schema(path)
            self.assertEqual(schema.get("kind"), "register_xlsx")
            self.assertEqual(schema.get("periodHints"), ["2026-07"])
            self.assertTrue(schema.get("hasInsurancePatientSplit"))
            summary = parse_softdent_register_xls(path)
            self.assertIsNotNone(summary)
            self.assertEqual(summary.get("period"), "2026-07")
            self.assertEqual(float(summary.get("insurance") or 0), 12000.0)
            self.assertEqual(float(summary.get("patient") or 0), 6000.0)
            self.assertTrue(summary.get("hasInsurancePatientSplit"))
            self.assertFalse(summary.get("collectionsFormatRequired"))

    def test_content_period_wins_over_filename_run_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Filename looks like July 1 run; body is June period (matches live SoftDent file).
            path = Path(tmp) / "RegisterForPeriodReportFor07012026.xlsx"
            _write_register_xlsx(
                path,
                period_line="06/01/26 thru 06/30/26",
                ins_plan=0.0,
                regular=108787.14,
            )
            schema = detect_daysheet_export_schema(path)
            self.assertEqual(schema.get("periodHints"), ["2026-06"])
            self.assertFalse(schema.get("hasInsurancePatientSplit"))
            summary = summarize_daysheet_export(path)
            self.assertEqual(summary.get("period"), "2026-06")
            self.assertEqual(float(summary.get("collections") or 0), 108787.14)
            self.assertEqual(float(summary.get("insurance") or 0), 0.0)
            # SoftDent labeled Regular Collections — patient side is truth, not invented.
            self.assertEqual(float(summary.get("patient") or 0), 108787.14)
            self.assertTrue(summary.get("regularCollectionsReported"))
            self.assertTrue(summary.get("registerInsPlanZero"))
            self.assertFalse(summary.get("collectionsFormatRequired"))
            classified = classify_daysheet_inbox_periods(
                [{"name": path.name, "path": str(path), "kind": "register"}]
            )
            self.assertIn("2026-06", classified.get("periods") or [])
            self.assertNotIn("2026-07", classified.get("periods") or [])

    def test_ingest_routes_xlsx_register(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "RegisterForPeriodReportFor07122026.xlsx"
            _write_register_xlsx(
                path,
                period_line="07/01/26 thru 07/12/26",
                ins_plan=9000.0,
                regular=3000.0,
            )
            dest = root / "out"
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
            self.assertIn("2026-07", (result.get("created") or []) + (result.get("updated") or []))
            rows = json.loads((dest / "softdent_dashboard_data.json").read_text(encoding="utf-8"))
            jul = next(r for r in rows if r.get("period") == "2026-07")
            self.assertEqual(float(jul.get("insurance") or 0), 9000.0)
            self.assertEqual(float(jul.get("patient") or 0), 3000.0)
            self.assertTrue(jul.get("collectionsReported"))
            self.assertNotIn("collectionsPending", jul)

    def test_live_xls_if_present(self):
        live = Path(r"C:\SoftDentReportExports\RegisterForPeriodReportFor07012026.xls")
        if not live.is_file():
            self.skipTest("live SoftDent Register XLS not present")
        summary = parse_softdent_register_xls(live)
        self.assertIsNotNone(summary)
        self.assertEqual(summary.get("period"), "2026-06")
        self.assertGreater(float(summary.get("production") or 0), 0)
        # Live SoftDent file reports Ins Plan $0 — insurance stays 0; Regular may be > 0.
        self.assertEqual(float(summary.get("insurance") or 0), 0.0)
        if summary.get("regularCollections") is not None:
            self.assertEqual(
                float(summary.get("patient") or 0),
                float(summary.get("regularCollections") or 0),
            )
            self.assertTrue(summary.get("registerInsPlanZero"))
        else:
            self.assertEqual(float(summary.get("patient") or 0), 0.0)


if __name__ == "__main__":
    unittest.main()
