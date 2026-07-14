"""HAL-10588 gold payment pipeline audit, ingest repair, BUILD_ID coupling."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID
from softdent_gold_payment_pipeline import (
    PACKAGE_BUILD_ID,
    audit_gold_payment_pipeline,
    export_gold_pipeline_report,
    find_gold_payment_candidates,
    format_gold_pipeline_reply,
    gold_payment_pipeline_widget,
    run_gold_payment_pipeline_repair,
    validate_exact_usable_cells,
)
from softdent_insco_ada_pct_variance import build_insco_ada_pct_variance, ensure_pct_variance_schema
from softdent_insco_ada_probabilistic import (
    build_insco_ada_probabilistic_estimates,
    ensure_probabilistic_schema,
)
from softdent_odbc_extract import ensure_sd_schema
from softdent_treatment_planning import ensure_treatment_planning_schema


_FIXTURE_CSV = """Insurance Company,Procedure Code,Submitted Fee,Allowed Amount,Paid Amount,Write Off,Patient Portion,Claim Number,Check Number,Payment Date,Description
DELTA DENTAL OF KS,D1110,140.00,112.00,84.00,28.00,28.00,C1,CHK1,2025-06-01,Prophy
DELTA DENTAL OF KS,D1110,140.00,112.00,90.00,22.00,22.00,C2,CHK2,2025-06-15,Prophy
DELTA DENTAL OF KS,D2740,1100.00,900.00,700.00,200.00,200.00,C3,CHK3,2025-05-01,Crown
"""


def _empty_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        ensure_sd_schema(conn)
        ensure_treatment_planning_schema(conn)
        ensure_probabilistic_schema(conn)
        ensure_pct_variance_schema(conn)
        conn.commit()
    finally:
        conn.close()


def _seed_spine(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        ensure_sd_schema(conn)
        ensure_probabilistic_schema(conn)
        ensure_pct_variance_schema(conn)
        ensure_treatment_planning_schema(conn)
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
            ) VALUES ('', '500500', 1, 'DELTA DENTAL OF KS', 'now')
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
                        f"t{rn}",
                        rn,
                        "500500",
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
        build_insco_ada_probabilistic_estimates(conn, years=5)
        build_insco_ada_pct_variance(conn, years=5)
        conn.commit()
    finally:
        conn.close()


class GoldPaymentPipelineHal10588Tests(unittest.TestCase):
    def test_build_id_coupled_to_package(self) -> None:
        self.assertEqual(PACKAGE_BUILD_ID, "hal-10588")
        self.assertEqual(BUILD_ID, "hal-10628")

    def test_audit_diagnoses_missing_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "analytics.db"
            drop = root / "exports"
            drop.mkdir()
            _empty_db(db)
            audit = audit_gold_payment_pipeline(db_path=db, search_dir=drop)
            self.assertEqual(audit.get("gapCode"), "GOLD_CSV_MISSING")
            self.assertEqual(audit.get("paymentLines"), 0)
            self.assertIn("empty != $0", audit.get("honesty") or "")
            self.assertFalse(audit.get("candidates"))

    def test_fixture_csv_ingest_via_repair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "analytics.db"
            drop = root / "exports"
            drop.mkdir()
            _empty_db(db)
            csv_path = drop / "insurance_payments_20260712.csv"
            csv_path.write_text(_FIXTURE_CSV, encoding="utf-8")

            cands = find_gold_payment_candidates(search_dir=drop)
            self.assertEqual(len(cands), 1)

            repaired = run_gold_payment_pipeline_repair(db_path=db, search_dir=drop)
            self.assertTrue(repaired.get("ok"))
            audit = repaired.get("audit") or {}
            self.assertEqual(audit.get("gapCode"), "GOLD_OK")
            self.assertGreaterEqual(int(audit.get("paymentLines") or 0), 3)
            self.assertGreaterEqual(int(repaired.get("ingest", {}).get("paymentLines") or 0), 3)

            conn = sqlite3.connect(str(db))
            try:
                n = conn.execute("SELECT COUNT(*) FROM sd_insurance_payment_lines").fetchone()[0]
                est = conn.execute("SELECT COUNT(*) FROM treatment_planning_estimates").fetchone()[0]
            finally:
                conn.close()
            self.assertGreaterEqual(n, 3)
            self.assertGreaterEqual(est, 1)

    def test_file_present_not_ingested_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "analytics.db"
            drop = root / "exports"
            drop.mkdir()
            _empty_db(db)
            # Odd name still found by candidate token hunt, but not by payment globs
            bad = drop / "inspay_odd_drop.csv"
            bad.write_text("not,a,valid,payment,header\nx,y,z,a,b\n", encoding="utf-8")
            audit = audit_gold_payment_pipeline(db_path=db, search_dir=drop)
            self.assertEqual(audit.get("gapCode"), "GOLD_FILE_PRESENT_NOT_INGESTED")

    def test_exact_usable_spine_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "analytics.db"
            _seed_spine(db)
            validation = validate_exact_usable_cells(db_path=db)
            self.assertTrue(validation.get("ok"))
            self.assertGreaterEqual(int(validation.get("cellsChecked") or 0), 1)
            self.assertFalse(validation.get("remittanceAvailable"))
            self.assertGreaterEqual(int(validation.get("passCount") or 0), 1)

    def test_export_report_and_reply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "analytics.db"
            dest = root / "out"
            drop = root / "exports"
            drop.mkdir()
            _seed_spine(db)
            rep = export_gold_pipeline_report(db_path=db, dest=dest, search_dir=drop)
            self.assertTrue(rep.get("ok"))
            self.assertTrue(Path(rep["jsonPath"]).is_file())
            self.assertTrue(Path(rep["mdPath"]).is_file())
            text = format_gold_pipeline_reply(
                audit_gold_payment_pipeline(db_path=db, search_dir=drop)
            )
            self.assertIn("HAL-10588", text)
            self.assertIn("empty != $0", text)

    def test_widget_empty_tone(self) -> None:
        # Live widget against real env — only assert shape / honesty when CSV missing
        w = gold_payment_pipeline_widget()
        self.assertEqual(w.get("id"), "softdent-gold-payment-pipeline")
        self.assertEqual(w.get("packageBuildId"), "hal-10588")
        self.assertIn("honesty", w)

    def test_candidate_scan_ingest_path(self) -> None:
        """File matches token hunt but not payment globs → candidate ingest path."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "analytics.db"
            drop = root / "exports"
            drop.mkdir()
            _empty_db(db)
            csv_path = drop / "inspay_delta_lines.csv"
            csv_path.write_text(_FIXTURE_CSV, encoding="utf-8")
            repaired = run_gold_payment_pipeline_repair(db_path=db, search_dir=drop)
            self.assertGreaterEqual(
                int((repaired.get("ingest") or {}).get("paymentLines") or 0), 3
            )
            self.assertEqual((repaired.get("audit") or {}).get("gapCode"), "GOLD_OK")

    def test_exact_cell_flag_on_negative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "analytics.db"
            _seed_spine(db)
            conn = sqlite3.connect(str(db))
            try:
                conn.execute(
                    """
                    UPDATE insco_ada_probabilistic_estimates
                    SET paid_median = -1.0
                    WHERE tier='exact' AND credibility IN ('high','usable')
                    """
                )
                conn.commit()
            finally:
                conn.close()
            validation = validate_exact_usable_cells(db_path=db)
            self.assertGreaterEqual(int(validation.get("flagCount") or 0), 1)


if __name__ == "__main__":
    unittest.main()
