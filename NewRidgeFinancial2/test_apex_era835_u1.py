"""Phase U1 validation — ERA 835 aggregate ingest (no PHI, no SoftDent write-back)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID, build_apex_widgets
from apex_era835_pack import (
    GAP_ERA835_PENDING,
    assess_era835_gap,
    era835_enabled,
    ingest_era835_to_unified,
    list_era835_payments,
    parse_era835_text,
)

SAMPLE_X12 = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *260711*1200*^*00501*000000001*0*P*:~
GS*HP*SENDER*RECEIVER*20260711*1200*1*X*005010X221A1~
ST*835*0001~
BPR*I*225.00*C*CHK************20260710~
N1*PR*DELTA DENTAL OF KANSAS~
N1*PE*NEW RIDGE FAMILY~
CLP*CLAIM1*1*200*150**12*1~
NM1*QC*1*DOE*JANE~
CAS*CO*45*50~
SVC*AD:D1110*100*75~
CLP*CLAIM2*1*100*75**12*2~
SVC*AD:D0120*100*75~
SE*20*0001~
GE*1*1~
IEA*1*000000001~
"""

SAMPLE_CSV = """Payer,CheckDate,Paid,AdjCode,ProcCode,Patient
Delta Dental,2026-07-10,150.00,CO45,D1110,ShouldNotStore
MetLife,2026-07-10,80.00,PR1,D0120,AlsoDrop
"""


class Era835PhaseU1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self._tmpdir.name) / "nr2_unified_u1.db"

    def tearDown(self) -> None:
        try:
            self._tmpdir.cleanup()
        except Exception:
            pass

    def test_build_id(self):
        self.assertEqual(BUILD_ID, "hal-10483")

    def test_flag_default_on(self):
        prev = os.environ.pop("NR2_ERA835", None)
        try:
            self.assertTrue(era835_enabled())
        finally:
            if prev is not None:
                os.environ["NR2_ERA835"] = prev

    def test_parse_x12_discards_patient(self):
        parsed = parse_era835_text(SAMPLE_X12)
        self.assertTrue(parsed.get("ok"))
        blob = str(parsed)
        self.assertNotIn("DOE", blob)
        self.assertNotIn("JANE", blob)
        self.assertEqual(parsed.get("payer_name"), "DELTA DENTAL OF KANSAS")
        self.assertGreaterEqual(int(parsed.get("claim_count") or 0), 2)
        self.assertIn("CO45", parsed.get("adjustment_reasons") or {})

    def test_parse_csv_discards_patient_column(self):
        parsed = parse_era835_text(SAMPLE_CSV)
        self.assertTrue(parsed.get("ok"))
        blob = str(parsed)
        self.assertNotIn("ShouldNotStore", blob)
        self.assertNotIn("AlsoDrop", blob)
        self.assertGreaterEqual(int(parsed.get("claim_count") or 0), 2)

    def test_pending_empty(self):
        parsed = parse_era835_text("")
        self.assertTrue(parsed.get("pending"))
        self.assertEqual(parsed.get("gap"), GAP_ERA835_PENDING)

    def test_ingest_unified(self):
        result = ingest_era835_to_unified(
            content=SAMPLE_X12,
            filename="sample.835",
            db_path=self.db_path,
        )
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("phase"), "U1")
        self.assertFalse(result.get("softDentWriteBack"))
        rows = list_era835_payments(limit=10, db_path=self.db_path)
        self.assertTrue(rows)
        self.assertTrue(all("payerName" in r for r in rows))
        blob = str(rows)
        self.assertNotIn("DOE", blob)
        self.assertNotIn("JANE", blob)

    def test_gap_widget(self):
        gap = assess_era835_gap(db_path=self.db_path)
        self.assertEqual(gap.get("gapCode"), GAP_ERA835_PENDING)
        out = build_apex_widgets("softdent")
        ids = {w.get("id") for w in (out.get("widgets") or []) if isinstance(w, dict)}
        self.assertIn("era835-ingest-gap", ids)

    def test_disabled(self):
        prev = os.environ.get("NR2_ERA835")
        os.environ["NR2_ERA835"] = "0"
        try:
            result = ingest_era835_to_unified(content=SAMPLE_X12, db_path=self.db_path)
            self.assertFalse(result.get("ok"))
            self.assertEqual(result.get("reason"), "era835_disabled")
        finally:
            if prev is None:
                os.environ.pop("NR2_ERA835", None)
            else:
                os.environ["NR2_ERA835"] = prev


if __name__ == "__main__":
    unittest.main()
