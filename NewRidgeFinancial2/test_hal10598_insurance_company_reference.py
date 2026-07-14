"""HAL-10598 — SoftDent insurance company master CSV ingest."""

from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID
from softdent_insurance_company_reference import (
    PACKAGE_BUILD_ID,
    ingest_insurance_companies_csv,
    insurance_company_reference_status,
    list_likely_active_companies,
)
from softdent_odbc_extract import ensure_sd_schema


_CSV = """company_name,status,record_number,address1,address2,zip
"DELTA DENTAL OF KS","likely_active","1","PO BOX 1","","66629"
"DISC - OLD CO","discontinued","2","PO BOX 2","","00000"
"METLIFE DENTAL","likely_active","3","PO BOX 3","","10001"
"""


class InsuranceCompanyReferenceHal10598Tests(unittest.TestCase):
    def test_build_id_coupled(self) -> None:
        self.assertEqual(PACKAGE_BUILD_ID, "hal-10598")
        self.assertEqual(BUILD_ID, "hal-10608")

    def test_ingest_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "a.db"
            csv_path = root / "softdent_insurance_companies.csv"
            csv_path.write_text(_CSV, encoding="utf-8")
            conn = sqlite3.connect(str(db))
            try:
                ensure_sd_schema(conn)
                conn.commit()
            finally:
                conn.close()
            result = ingest_insurance_companies_csv(
                csv_path=csv_path, db_path=db, copy_to_exports=False
            )
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("inserted"), 3)
            self.assertEqual(result.get("likelyActive"), 2)
            self.assertEqual(result.get("discontinued"), 1)
            st = insurance_company_reference_status(db_path=db)
            self.assertTrue(st.get("ok"))
            self.assertEqual(st.get("likelyActive"), 2)
            names = list_likely_active_companies(db_path=db)
            self.assertIn("DELTA DENTAL OF KS", names)
            self.assertNotIn("DISC - OLD CO", names)


if __name__ == "__main__":
    unittest.main()
