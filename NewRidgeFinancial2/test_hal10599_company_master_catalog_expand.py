"""HAL-10599 — Expand InsCo×ADA staff catalog to SoftDent company master."""

from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID
from softdent_insco_ada_catalog_matrix import (
    PACKAGE_BUILD_ID,
    expand_catalog_rows_with_company_master,
    export_catalog_matrix_report,
    list_catalog_matrix_rows,
)
from softdent_insco_ada_pct_variance import build_insco_ada_pct_variance, ensure_pct_variance_schema
from softdent_insco_ada_probabilistic import (
    build_insco_ada_probabilistic_estimates,
    ensure_probabilistic_schema,
)
from softdent_insurance_company_reference import (
    ensure_insurance_company_reference_schema,
    ingest_insurance_companies_csv,
)
from softdent_odbc_extract import ensure_sd_schema


def _seed(db: Path) -> None:
    conn = sqlite3.connect(str(db))
    try:
        ensure_sd_schema(conn)
        ensure_probabilistic_schema(conn)
        ensure_pct_variance_schema(conn)
        ensure_insurance_company_reference_schema(conn)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sd_account_transactions (
                stable_id TEXT PRIMARY KEY,
                source_file TEXT,
                row_number INTEGER,
                account_num TEXT,
                patient_name TEXT,
                service_date TEXT,
                provider TEXT,
                procedure TEXT,
                note_flag TEXT,
                amount REAL,
                prod REAL,
                charges REAL,
                prod_adj REAL,
                cash REAL,
                "check" REAL,
                credit REAL,
                pay_adj REAL,
                period_start TEXT,
                period_end TEXT,
                extracted_at TEXT
            );
            """
        )
        conn.execute(
            """
            INSERT INTO sd_patient_insurance (
                practice_id, patient_id, priority, insurance_name, extracted_at
            ) VALUES ('', '400400', 1, 'DELTA DENTAL OF KS', 'now')
            """
        )
        rn = 1
        for i in range(12):
            day = f"2025-{(i % 9) + 1:02d}-{(i % 27) + 1:02d}"
            for proc, billed, prod_adj, paid in (
                ("1110", 140.0, None, None),
                ("51", None, -28.0, None),
                ("2", None, None, 84.0),
            ):
                conn.execute(
                    """
                    INSERT INTO sd_account_transactions (
                        stable_id, source_file, row_number, account_num, patient_name,
                        service_date, provider, procedure, note_flag, amount,
                        prod, charges, prod_adj, cash, "check", credit, pay_adj,
                        period_start, period_end, extracted_at
                    ) VALUES (?, 't', ?, ?, 'Test', ?, '', ?, 'A', ?, ?, NULL, ?, NULL, ?, NULL, NULL,
                              '2021-01-01', '2026-07-01', 'now')
                    """,
                    (
                        f"s{rn}",
                        rn,
                        "400400",
                        day,
                        proc,
                        billed or prod_adj or paid,
                        billed,
                        prod_adj,
                        paid,
                    ),
                )
                rn += 1
        conn.commit()
        build_insco_ada_probabilistic_estimates(conn)
        build_insco_ada_pct_variance(conn, years=5)
        conn.commit()
    finally:
        conn.close()


class InscoAdaCompanyMasterExpandHal10599Tests(unittest.TestCase):
    def test_build_id_coupled(self) -> None:
        self.assertEqual(PACKAGE_BUILD_ID, "hal-10599")
        self.assertEqual(BUILD_ID, "hal-10608")

    def test_expand_pads_master_companies_with_null_dollars(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "a.db"
            _seed(db)
            csv_path = root / "companies.csv"
            csv_path.write_text(
                "company_name,status,record_number\n"
                '"DELTA DENTAL OF KS","likely_active","1"\n'
                '"METLIFE DENTAL","likely_active","2"\n'
                '"OLD DISC","discontinued","3"\n',
                encoding="utf-8",
            )
            ingest_insurance_companies_csv(
                csv_path=csv_path, db_path=db, copy_to_exports=False
            )
            spine = list_catalog_matrix_rows(
                db_path=db, include_insufficient=True, include_inferred=True, limit=100000
            )
            expanded = expand_catalog_rows_with_company_master(spine, db_path=db)
            self.assertGreater(len(expanded), len(spine))
            metlife = [
                r
                for r in expanded
                if str(r.get("insuranceCompany") or "").upper() == "METLIFE DENTAL"
            ]
            self.assertTrue(metlife)
            for r in metlife:
                self.assertEqual(r.get("credibility"), "no_settlement")
                self.assertIsNone(r.get("paidMedian"))
                self.assertIsNone(r.get("paidMedianCents"))
                self.assertIsNone(r.get("paidPctMedian"))
            # discontinued not in company universe
            disc = [
                r
                for r in expanded
                if "OLD DISC" in str(r.get("insuranceCompany") or "").upper()
            ]
            self.assertEqual(disc, [])

            export = export_catalog_matrix_report(db_path=db, dest=root)
            self.assertTrue(export.get("ok"))
            self.assertGreaterEqual(int(export.get("noSettlementPadCells") or 0), 1)
            with Path(export["csvPath"]).open(encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), export.get("cellCount"))


if __name__ == "__main__":
    unittest.main()
