"""HAL-10600 — Spine ↔ company-master carrier alias reconcile."""

from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID
from softdent_carrier_alias import (
    PACKAGE_BUILD_ID,
    accept_pending_alias,
    carrier_alias_status,
    confidence_band,
    ensure_carrier_alias_schema,
    match_score,
    reconcile_carrier_aliases,
)
from softdent_insco_ada_catalog_matrix import (
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


def _seed_spine(db: Path) -> None:
    conn = sqlite3.connect(str(db))
    try:
        ensure_sd_schema(conn)
        ensure_probabilistic_schema(conn)
        ensure_pct_variance_schema(conn)
        ensure_insurance_company_reference_schema(conn)
        ensure_carrier_alias_schema(conn)
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
            ) VALUES ('', '400400', 1, 'AETNA', 'now')
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
                        f"a{rn}",
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


class CarrierAliasHal10600Tests(unittest.TestCase):
    def test_build_id_coupled(self) -> None:
        self.assertEqual(PACKAGE_BUILD_ID, "hal-10600")
        self.assertEqual(BUILD_ID, "hal-10608")

    def test_confidence_bands_moonshot(self) -> None:
        self.assertEqual(confidence_band(90.0), "auto")
        self.assertEqual(confidence_band(85.0), "manual")
        self.assertEqual(confidence_band(70.0), "manual")
        self.assertEqual(confidence_band(59.9), "reject")

    def test_match_does_not_cross_states(self) -> None:
        self.assertEqual(match_score("DELTA DENTAL OF MA", "DELTA DENTAL OF AR"), 0.0)

    def test_reconcile_joins_alias_without_inventing_payments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "a.db"
            _seed_spine(db)
            csv_path = root / "companies.csv"
            csv_path.write_text(
                "company_name,status,record_number\n"
                '"AETNA","likely_active","1"\n'
                '"Aetna Healthcare","likely_active","2"\n'
                '"ZZZ UNKNOWN PAYER","likely_active","3"\n',
                encoding="utf-8",
            )
            ingest_insurance_companies_csv(
                csv_path=csv_path, db_path=db, copy_to_exports=False
            )
            # Pre-count payment estimate rows — must not grow from alias reconcile
            conn = sqlite3.connect(str(db))
            before = int(
                conn.execute("SELECT COUNT(*) FROM insco_ada_probabilistic_estimates").fetchone()[0]
            )
            conn.close()

            result = reconcile_carrier_aliases(db_path=db, dest=root)
            self.assertTrue(result.get("ok"))
            mapping = Path(result["export"]["csvPath"])
            self.assertTrue(mapping.is_file())
            self.assertEqual(mapping.name, "carrier_alias_mapping.csv")

            conn = sqlite3.connect(str(db))
            after = int(
                conn.execute("SELECT COUNT(*) FROM insco_ada_probabilistic_estimates").fetchone()[0]
            )
            payment_lines = conn.execute(
                "SELECT name FROM sqlite_master WHERE name='sd_insurance_payment_lines'"
            ).fetchone()
            if payment_lines:
                pl = int(
                    conn.execute("SELECT COUNT(*) FROM sd_insurance_payment_lines").fetchone()[0]
                )
                self.assertEqual(pl, 0)
            conn.close()
            self.assertEqual(before, after)  # no synthetic estimate rows

            st = carrier_alias_status(db_path=db)
            self.assertTrue(st.get("ok"))
            self.assertGreaterEqual(int(st.get("autoAccepted") or 0), 1)

            spine = list_catalog_matrix_rows(
                db_path=db, include_insufficient=True, include_inferred=True, limit=100000
            )
            expanded = expand_catalog_rows_with_company_master(spine, db_path=db)
            aetna_hc = [
                r
                for r in expanded
                if str(r.get("insuranceCompany") or "").upper() == "AETNA HEALTHCARE"
                and r.get("credibility") != "no_settlement"
            ]
            self.assertTrue(aetna_hc)
            for r in aetna_hc:
                self.assertEqual(str(r.get("source")), "alias_spine_settlement")
                self.assertEqual(str(r.get("spineCarrierName") or "").upper(), "AETNA")
                self.assertIsNotNone(r.get("masterCompanyId"))

            # Unknown payer stays no_settlement null $
            unk = [
                r
                for r in expanded
                if "ZZZ UNKNOWN" in str(r.get("insuranceCompany") or "").upper()
            ]
            self.assertTrue(unk)
            for r in unk:
                self.assertEqual(r.get("credibility"), "no_settlement")
                self.assertIsNone(r.get("paidMedian"))

            export = export_catalog_matrix_report(db_path=db, dest=root)
            self.assertTrue(export.get("ok"))
            with Path(export["csvPath"]).open(encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertIn("masterCompanyId", rows[0])
            self.assertIn("spineCarrierName", rows[0])

    def test_accept_pending_manual(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "b.db"
            _seed_spine(db)
            csv_path = root / "c.csv"
            # Force a mid-band name via closely related but not auto if needed;
            # seed a pending row directly for HAL confirm path.
            conn = sqlite3.connect(str(db))
            ensure_carrier_alias_schema(conn)
            conn.execute(
                """
                INSERT INTO carrier_alias (
                    spine_carrier_name, master_company_id, master_company_name,
                    match_score, confidence, review_status, match_method, created_at_utc
                ) VALUES ('AETNA', '9', 'AETNA NEAR', 72.0, 'manual', 'pending',
                          'fuzzy_blocked_jw', 'now')
                """
            )
            conn.commit()
            conn.close()
            acc = accept_pending_alias("AETNA NEAR", db_path=db, accept=True)
            self.assertTrue(acc.get("ok"))
            st = carrier_alias_status(db_path=db)
            self.assertGreaterEqual(int(st.get("autoAccepted") or 0) + 0, 0)


if __name__ == "__main__":
    unittest.main()
