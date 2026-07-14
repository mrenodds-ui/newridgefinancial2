"""HAL-10595 / money-bridge-bijection — bijective cents + history dual-write."""

from __future__ import annotations

import random
import sqlite3
import tempfile
import unittest
import warnings
from decimal import Decimal
from pathlib import Path

from apex_backend import BUILD_ID
from money_cents import (
    cents_int_to_money,
    money_to_api,
    money_to_api_bijective,
    to_money,
)
from softdent_odbc_extract import ensure_sd_schema
from softdent_print_preview_audit import append_print_preview_audit
from softdent_treatment_planning import ensure_treatment_planning_schema
from softdent_visual_ledger_recon import (
    PACKAGE_BUILD_ID,
    append_recon_variance_history,
    list_recon_variance_history,
    migrate_history_to_exact,
    reconcile_visual_vs_ledger,
    visual_ledger_recon_widget,
)


class MoneyBridgeBijectionHal10595Tests(unittest.TestCase):
    def test_build_id_coupled(self) -> None:
        self.assertEqual(PACKAGE_BUILD_ID, "hal-10595")
        self.assertEqual(BUILD_ID, "hal-10608")
        # Visual-ledger package id stays 10595; global BUILD advanced with catalog package


    def test_money_to_api_deprecated_warns(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            out = money_to_api(Decimal("12.34"))
        self.assertEqual(out, 12.34)
        self.assertTrue(any(issubclass(w.category, DeprecationWarning) for w in caught))

    def test_bijective_boundaries(self) -> None:
        boundaries = [
            Decimal("0.01"),
            Decimal("999999.99"),
            # 2^53+1 cents as dollars
            (Decimal(2**53 + 1) / Decimal(100)).quantize(Decimal("0.01")),
        ]
        for d in boundaries:
            cents = money_to_api_bijective(d, format="cents_int")
            self.assertIsInstance(cents, int)
            back = cents_int_to_money(cents)  # type: ignore[arg-type]
            self.assertEqual(back, d)
            s = money_to_api_bijective(d, format="string_decimal")
            self.assertEqual(to_money(s), d)

    def test_bijective_random_cents(self) -> None:
        rng = random.Random(10595)
        for _ in range(50):
            cents = rng.randint(0, 10_000_000)
            d = (Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"))
            got = money_to_api_bijective(d, format="cents_int")
            self.assertEqual(got, cents)
            self.assertEqual(cents_int_to_money(got), d)  # type: ignore[arg-type]

    def test_history_dual_writes_cents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            db = dest / "analytics.db"
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
            self.assertEqual(recon.get("ledgerTotalCents"), 4000)
            self.assertEqual(recon.get("totalCents"), 4000)
            hist = append_recon_variance_history(recon, db_path=db)
            self.assertTrue(hist.get("ok"))
            self.assertEqual(hist.get("totalCents"), 4000)
            listed = list_recon_variance_history(months=3, db_path=db)
            row = listed["rows"][0]
            self.assertEqual(row.get("ledgerTotalCents"), 4000)
            self.assertEqual(row.get("totalCents"), 4000)
            self.assertEqual(row.get("moneyCentsExact"), 4000)
            self.assertTrue(row.get("floatMoneyDeprecated"))
            # total_cents matches Decimal ledger sum exactly
            self.assertEqual(
                cents_int_to_money(row["totalCents"]),
                to_money(recon.get("ledgerTotal")),
            )

    def test_migrate_recomputes_not_from_real(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            db = dest / "analytics.db"
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
                conn.execute(
                    """
                    INSERT INTO sd_account_transactions
                    (account_num, service_date, procedure, row_number,
                     prod, charges, prod_adj, pay_adj, cash, "check", credit)
                    VALUES ('100', '2026-06-10', '2', 1, 0, 0, 0, 0, 0, 12.34, 0)
                    """
                )
                from softdent_visual_ledger_recon import ensure_recon_variance_history_schema

                ensure_recon_variance_history_schema(conn)
                # Legacy row: REAL only, cents NULL (lossy float present but must be ignored)
                conn.execute(
                    """
                    INSERT INTO recon_variance_history (
                        period_start, period_end, visual_total, ledger_total,
                        variance_dollars, scope_mismatch, result_code, created_at,
                        package_build_id, triggers_gold_ingest
                    ) VALUES (
                        '2026-06-01', '2026-06-30', 12.34, 12.34,
                        0.0, 0, 'MATCH', '2026-07-13T00:00:00+00:00',
                        'hal-10593', 0
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()
            append_print_preview_audit(
                {
                    "reportType": "InsuranceIncome",
                    "dateRange": "2026-06-01..2026-06-30",
                    "lastPageAggregateTotal": 12.34,
                    "pageCount": 1,
                    "operatorId": "test",
                },
                dest=dest,
            )
            mig = migrate_history_to_exact(db_path=db, dest=dest)
            self.assertTrue(mig.get("ok"))
            self.assertGreaterEqual(mig.get("updated") or 0, 1)
            listed = list_recon_variance_history(months=12, db_path=db)
            row = listed["rows"][0]
            self.assertEqual(row.get("ledgerTotalCents"), 1234)
            self.assertEqual(row.get("totalCents"), 1234)
            self.assertEqual(cents_int_to_money(1234), Decimal("12.34"))

    def test_widget_exposes_total_cents(self) -> None:
        w = visual_ledger_recon_widget()
        self.assertEqual(w.get("packageBuildId"), "hal-10595")
        self.assertIn("totalCents", w)
        self.assertTrue(w.get("floatMoneyDeprecated"))
        self.assertIn("HAL-10595", str(w.get("label") or ""))


if __name__ == "__main__":
    unittest.main()
