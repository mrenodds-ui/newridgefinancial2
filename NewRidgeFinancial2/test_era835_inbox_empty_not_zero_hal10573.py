"""Moonshot ERA-835 inbox scaffolding — empty ≠ $0 (hal-10576)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from apex_backend import BUILD_ID
from apex_era835_pack import (
    ensure_era_inbox_dirs,
    era_inbox_status,
    ingest_era_inbox,
    scan_era_inbox,
)
from apex_softdent_hardening_pack import (
    GAP_ERA_835_REQUIRED,
    assess_collections_gap,
    collections_gap_widget,
)
from apex_softdent_era_pack import enrich_collections_gap_with_era
from softdent_practice_exports import stub_era835_ingestion_path


def _bundle_register_ins_plan_zero() -> dict:
    return {
        "softdent": {
            "dashboard": {
                "rows": [
                    {
                        "period": "2026-07",
                        "year_month": "2026-07",
                        "production": 44735.0,
                        "collections": 30626.42,
                        "collectionsReported": True,
                        "collectionsPending": False,
                        "collectionsFormatRequired": True,
                        "insurance": 0.0,
                        "patient": 0.0,
                    }
                ]
            }
        }
    }


class Era835InboxScaffoldTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10576")

    def test_era835_inbox_empty_not_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "era"
            out = scan_era_inbox(roots=[root], ensure_dirs=True)
            self.assertTrue(out.get("ok"))
            self.assertTrue(out.get("empty"))
            self.assertEqual(out.get("honesty"), "empty_not_zero")
            self.assertEqual(out.get("files"), [])
            self.assertEqual(out.get("chipStatus"), "awaiting")
            self.assertIn("Awaiting", str(out.get("chipLabel") or ""))
            self.assertFalse(out.get("readyToIngest"))
            self.assertTrue(root.is_dir())
            self.assertFalse(out.get("writeBack"))
            # Never invent payment totals
            self.assertNotIn("paymentTotal", out)
            self.assertNotIn("insurance", out)

    def test_scan_lists_files_without_inventing_dollars(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "era"
            root.mkdir(parents=True)
            (root / "sample.835").write_text("ISA*00*", encoding="utf-8")
            out = scan_era_inbox(roots=[root], ensure_dirs=False)
            self.assertFalse(out.get("empty"))
            self.assertEqual(out.get("fileCount"), 1)
            self.assertEqual(out.get("chipStatus"), "ready")
            self.assertIn("Ready", str(out.get("chipLabel") or ""))
            self.assertEqual(out["files"][0]["name"], "sample.835")
            self.assertNotIn("paymentTotal", out["files"][0])

    def test_required_gap_unchanged_when_inbox_empty(self) -> None:
        gap = {
            "gapCode": GAP_ERA_835_REQUIRED,
            "collectionsGapCode": GAP_ERA_835_REQUIRED,
            "registerInsPlanZero": True,
            "period": "2026-07",
            "healthy": False,
            "collections": None,
            "issues": [],
        }
        with mock.patch(
            "apex_softdent_era_pack.era_available_for_period",
            return_value={"available": True, "paymentTotal": None, "claimCount": 4},
        ), mock.patch(
            "apex_era835_pack.scan_era_inbox",
            return_value={
                "empty": True,
                "chipStatus": "awaiting",
                "chipLabel": "Awaiting first 835 drop",
                "fileCount": 0,
                "existingRoots": [r"C:\SoftDentFinancialExports\era"],
                "honesty": "empty_not_zero",
            },
        ):
            enriched = enrich_collections_gap_with_era(gap)
        self.assertEqual(enriched.get("gapCode"), GAP_ERA_835_REQUIRED)
        self.assertEqual(enriched.get("collectionsGapCode"), GAP_ERA_835_REQUIRED)
        self.assertTrue((enriched.get("eraInbox") or {}).get("empty"))

    def test_widget_chip_awaits_drop(self) -> None:
        with mock.patch(
            "apex_era835_pack.scan_era_inbox",
            return_value={
                "empty": True,
                "chipStatus": "awaiting",
                "chipLabel": "Awaiting first 835 drop",
                "fileCount": 0,
            },
        ):
            w = collections_gap_widget(_bundle_register_ins_plan_zero())
        self.assertEqual(w.get("emptyMessage"), GAP_ERA_835_REQUIRED)
        labels = " ".join(str(c.get("label") or "") for c in (w.get("halChips") or []))
        self.assertIn("Awaiting first 835 drop", labels)
        self.assertNotIn("Re-export", labels)

    def test_stub_scaffold_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "era"
            with mock.patch(
                "apex_era835_pack.era_inbox_candidate_roots",
                return_value=[root],
            ):
                stub = stub_era835_ingestion_path()
        self.assertIn(stub.get("mode"), ("scaffold", "stub"))
        self.assertEqual(stub.get("honesty"), "empty_not_zero")
        self.assertTrue(stub.get("readOnly"))
        self.assertFalse(stub.get("writeBack"))

    def test_era_inbox_status_api_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "era"
            with mock.patch(
                "apex_era835_pack.era_inbox_candidate_roots",
                return_value=[root],
            ):
                st = era_inbox_status(ensure_dirs=True)
        self.assertTrue(st.get("ok"))
        self.assertEqual(st.get("honesty"), "empty_not_zero")
        self.assertTrue((st.get("inbox") or {}).get("empty"))

    def test_era835_single_file_ingest(self) -> None:
        sample = (
            "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
            "*260711*1200*^*00501*000000001*0*P*:~\n"
            "GS*HP*SENDER*RECEIVER*20260711*1200*1*X*005010X221A1~\n"
            "ST*835*0001~\n"
            "BPR*I*225.00*C*CHK************20260710~\n"
            "N1*PR*DELTA DENTAL OF KANSAS~\n"
            "CLP*CLAIM1*1*200*150**12*1~\n"
            "NM1*QC*1*DOE*JANE~\n"
            "SVC*AD:D1110*100*75~\n"
            "SE*10*0001~\n"
            "GE*1*1~\n"
            "IEA*1*000000001~\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "era"
            root.mkdir(parents=True)
            (root / "drop.835").write_text(sample, encoding="utf-8")
            db = Path(tmp) / "nr2_unified_inbox.db"
            out = ingest_era_inbox(roots=[root], db_path=db, ensure_dirs=False)
            self.assertTrue(out.get("ok"))
            self.assertFalse(out.get("empty"))
            self.assertEqual(out.get("honesty"), "empty_not_zero")
            self.assertFalse(out.get("writeBack"))
            self.assertFalse(out.get("softDentWriteBack"))
            self.assertEqual(out.get("chipStatus"), "ready")
            self.assertEqual(len(out.get("ingested") or []), 1)
            row = (out.get("ingested") or [])[0]
            self.assertTrue(row.get("ok"))
            self.assertEqual(row.get("name"), "drop.835")
            self.assertGreaterEqual(int(row.get("rowsInserted") or 0), 1)

    def test_ingest_empty_inbox_stays_awaiting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "era"
            out = ingest_era_inbox(roots=[root], ensure_dirs=True)
            self.assertTrue(out.get("ok"))
            self.assertTrue(out.get("empty"))
            self.assertEqual(out.get("chipStatus"), "awaiting")
            self.assertEqual(out.get("ingested"), [])
            self.assertNotIn("paymentTotal", out)


if __name__ == "__main__":
    unittest.main()
