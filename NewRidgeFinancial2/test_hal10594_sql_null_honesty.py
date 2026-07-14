"""HAL-10594 / sql-null-honesty — NULL-preserving ledger + fingerprint tests.

Module BUILD_ID advanced to HAL-10595; 10594 SQL-null behaviors still covered.
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID
from softdent_odbc_extract import ensure_sd_schema
from softdent_print_preview_audit import append_print_preview_audit
from softdent_treatment_planning import ensure_treatment_planning_schema
from softdent_visual_ledger_recon import (
    PACKAGE_BUILD_ID,
    append_recon_variance_history,
    reconcile_visual_vs_ledger,
    sum_ledger_code2_by_carrier,
    sum_ledger_code2_payments,
    visual_ledger_recon_widget,
)


def _empty_tx_db(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db))
    ensure_sd_schema(conn)
    ensure_treatment_planning_schema(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sd_account_transactions (
            account_num TEXT, service_date TEXT, procedure TEXT,
            row_number INTEGER, prod REAL, charges REAL,
            prod_adj REAL, pay_adj REAL, cash REAL, "check" REAL,
            credit REAL, period_start TEXT, period_end TEXT, source_file TEXT
        )
        """
    )
    return conn


class SqlNullHonestyHal10594Tests(unittest.TestCase):
    def test_build_id_coupled(self) -> None:
        self.assertEqual(PACKAGE_BUILD_ID, "hal-10595")
        self.assertEqual(BUILD_ID, "hal-10608")
        # Visual-ledger package id stays 10595; global BUILD advanced with catalog package


    def test_ledger_all_null_returns_none(self) -> None:
        """Code-2 rows with all-null amounts must not become $0.00."""
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "analytics.db"
            conn = _empty_tx_db(db)
            try:
                conn.execute(
                    """
                    INSERT INTO sd_account_transactions
                    (account_num, service_date, procedure, row_number,
                     prod, charges, prod_adj, pay_adj, cash, "check", credit)
                    VALUES ('100', '2026-06-10', '2', 1, 0, 0, 0, 0, NULL, NULL, NULL)
                    """
                )
                conn.execute(
                    """
                    INSERT INTO sd_account_transactions
                    (account_num, service_date, procedure, row_number,
                     prod, charges, prod_adj, pay_adj, cash, "check", credit)
                    VALUES ('200', '2026-06-12', '2', 2, 0, 0, 0, 0, NULL, NULL, NULL)
                    """
                )
                conn.commit()
            finally:
                conn.close()

            out = sum_ledger_code2_payments(
                period_start="2026-06-01", period_end="2026-06-30", db_path=db
            )
            self.assertTrue(out.get("ok"))
            self.assertEqual(out.get("rowCount"), 2)
            self.assertIsNone(out.get("ledgerTotal"))
            self.assertIn("empty != $0", str(out.get("message") or ""))

    def test_carrier_skips_null_amounts_no_zero_unmapped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "analytics.db"
            conn = _empty_tx_db(db)
            try:
                conn.execute(
                    """
                    INSERT INTO sd_account_transactions
                    (account_num, service_date, procedure, row_number,
                     prod, charges, prod_adj, pay_adj, cash, "check", credit)
                    VALUES ('999', '2026-06-10', '2', 1, 0, 0, 0, 0, NULL, NULL, NULL)
                    """
                )
                conn.commit()
            finally:
                conn.close()
            carriers = sum_ledger_code2_by_carrier(
                period_start="2026-06-01", period_end="2026-06-30", db_path=db
            )
            self.assertTrue(carriers.get("ok"))
            self.assertEqual(carriers.get("carrierBreakdown") or [], [])
            self.assertIsNone(carriers.get("breakdownTotal"))
            self.assertGreaterEqual(int(carriers.get("skippedNullAmounts") or 0), 1)

    def test_record_fingerprint_collision_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            db = dest / "analytics.db"
            conn = _empty_tx_db(db)
            try:
                conn.execute(
                    """
                    INSERT INTO sd_account_transactions
                    (account_num, service_date, procedure, row_number,
                     prod, charges, prod_adj, pay_adj, cash, "check", credit)
                    VALUES ('100', '2026-06-10', '2', 1, 0, 0, 0, 0, 0, 40.0, 0)
                    """
                )
                conn.commit()
            finally:
                conn.close()
            append_print_preview_audit(
                {
                    "reportType": "InsuranceIncome",
                    "dateRange": "2026-06-01..2026-06-30",
                    "lastPageAggregateTotal": 40.0,
                    "pageCount": 1,
                    "operatorId": "test",
                },
                dest=dest,
            )
            recon = reconcile_visual_vs_ledger(period="2026-06", dest=dest, db_path=db)
            first = append_recon_variance_history(recon, db_path=db)
            self.assertTrue(first.get("ok"))
            self.assertIn("recordFingerprint", first)
            second = append_recon_variance_history(recon, db_path=db)
            self.assertFalse(second.get("ok"))
            self.assertIn("record_fingerprint_collision", str(second.get("error") or ""))

    def test_widget_package(self) -> None:
        w = visual_ledger_recon_widget()
        self.assertEqual(w.get("packageBuildId"), "hal-10595")
        self.assertEqual(w.get("def"), "HAL-10595")
        self.assertIn("HAL-10595", str(w.get("label") or ""))
        self.assertFalse(w.get("triggersGoldIngest"))


if __name__ == "__main__":
    unittest.main()
