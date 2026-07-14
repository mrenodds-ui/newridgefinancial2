"""HAL-10593 / HON-003 — carrier breakdown, period clamp, variance history."""

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
    list_recon_variance_history,
    reconcile_visual_vs_ledger,
    run_ops_10593_visual_ledger_recon,
    sum_ledger_code2_by_carrier,
    visual_ledger_recon_widget,
)


def _seed_tx_db(db: Path) -> None:
    conn = sqlite3.connect(str(db))
    try:
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
        # June: two carriers; July extra payment for clamp diagnostics
        conn.executemany(
            """
            INSERT INTO sd_account_transactions
            (account_num, service_date, procedure, row_number,
             prod, charges, prod_adj, pay_adj, cash, "check", credit)
            VALUES (?, ?, '2', 1, 0, 0, 0, 0, 0, ?, 0)
            """,
            [
                ("100", "2026-06-10", 40.0),
                ("200", "2026-06-15", 58.0),
                ("100", "2026-07-05", 25.0),
            ],
        )
        conn.executemany(
            """
            INSERT INTO sd_patient_insurance
            (practice_id, patient_id, priority, insurance_name, extracted_at)
            VALUES ('', ?, 1, ?, '2026-07-13T00:00:00+00:00')
            """,
            [("100", "DELTA DENTAL"), ("200", "METLIFE")],
        )
        conn.commit()
    finally:
        conn.close()


class VisualLedgerReconHal10593Tests(unittest.TestCase):
    def test_build_id_coupled(self) -> None:
        # Module advanced to hal-10595; prior 10593 behaviors still covered below
        self.assertEqual(PACKAGE_BUILD_ID, "hal-10595")
        self.assertEqual(BUILD_ID, "hal-10608")
        # Visual-ledger package id stays 10595; global BUILD advanced with catalog package


    def test_carrier_breakdown_sums_to_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            db = dest / "analytics.db"
            _seed_tx_db(db)
            carriers = sum_ledger_code2_by_carrier(
                period_start="2026-06-01", period_end="2026-06-30", db_path=db
            )
            self.assertTrue(carriers.get("ok"))
            self.assertEqual(carriers.get("breakdownTotal"), 98.0)
            codes = {c["carrierCode"] for c in carriers["carrierBreakdown"]}
            self.assertIn("DELTA DENTAL", codes)
            self.assertIn("METLIFE", codes)
            self.assertEqual(
                sum(c["amount"] for c in carriers["carrierBreakdown"]),
                98.0,
            )

    def test_clamp_on_scope_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            db = dest / "analytics.db"
            _seed_tx_db(db)
            append_print_preview_audit(
                {
                    "reportType": "InsuranceIncome",
                    # Narrower than full month request → scopeMismatch
                    "dateRange": "2026-06-15..2026-06-30",
                    "lastPageAggregateTotal": 100.0,
                    "pageCount": 2,
                    "operatorId": "test",
                },
                dest=dest,
            )
            recon = reconcile_visual_vs_ledger(period="2026-06", dest=dest, db_path=db)
            self.assertTrue(recon.get("scopeMismatch"))
            # Requested full June: 40 + 58 = 98
            self.assertEqual(recon.get("ledgerTotal"), 98.0)
            # Clamp to audit 06-15..06-30: only 58
            self.assertEqual(recon.get("clampedLedgerTotal"), 58.0)
            self.assertFalse(recon.get("triggersGoldIngest"))
            carriers = recon.get("carrierBreakdown") or []
            self.assertTrue(carriers)
            self.assertAlmostEqual(
                sum(float(c["amount"]) for c in carriers),
                98.0,
                places=2,
            )

    def test_history_persist_and_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            db = dest / "analytics.db"
            _seed_tx_db(db)
            append_print_preview_audit(
                {
                    "reportType": "InsuranceIncome",
                    "dateRange": "2026-06-01..2026-06-30",
                    "lastPageAggregateTotal": 100.0,
                    "pageCount": 1,
                    "operatorId": "test",
                },
                dest=dest,
            )
            run = run_ops_10593_visual_ledger_recon(
                period="2026-06", dest=dest, db_path=db, persist_history=True
            )
            self.assertTrue(run.get("ok"))
            self.assertTrue((run.get("historyAppend") or {}).get("ok"))
            hist = list_recon_variance_history(months=3, db_path=db)
            self.assertGreaterEqual(hist.get("count") or 0, 1)
            row = hist["rows"][0]
            self.assertIn("topCarrierCode", row)
            self.assertNotIn("patient", str(row).lower())
            self.assertEqual(row.get("packageBuildId"), "hal-10595")

    def test_widget_shows_carrier_and_clamp_fields(self) -> None:
        w = visual_ledger_recon_widget()
        self.assertEqual(w.get("packageBuildId"), "hal-10595")
        self.assertIn("carrierBreakdown", w)
        self.assertIn("clampedLedgerTotal", w)
        self.assertFalse(w.get("triggersGoldIngest"))
        self.assertTrue(w.get("ok"))


if __name__ == "__main__":
    unittest.main()
