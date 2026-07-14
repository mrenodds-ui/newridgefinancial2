"""HAL-10592 / HON-002 — Visual-audit × ledger reconciliation tests."""

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
    ReconciliationResult,
    classify_variance,
    format_visual_ledger_recon_reply,
    parse_date_range,
    reconcile_visual_vs_ledger,
    run_ops_10592_visual_ledger_recon,
    sum_ledger_code2_payments,
    visual_ledger_recon_widget,
)


class VisualLedgerReconHal10592Tests(unittest.TestCase):
    def test_build_id_coupled(self) -> None:
        # Module package remains HAL-10595; global BUILD_ID advanced to 10596
        self.assertEqual(PACKAGE_BUILD_ID, "hal-10595")
        self.assertEqual(BUILD_ID, "hal-10608")

    def test_parse_date_range_month_and_span(self) -> None:
        self.assertEqual(parse_date_range("2026-06"), ("2026-06-01", "2026-06-30"))
        self.assertEqual(
            parse_date_range("2026-06-01..2026-06-30"),
            ("2026-06-01", "2026-06-30"),
        )

    def test_parse_date_range_rejects_invalid_calendar(self) -> None:
        # Moonshot acceptance: invalid calendar → (None, None), never ValueError
        self.assertEqual(parse_date_range("2026-02-30"), (None, None))
        self.assertEqual(parse_date_range("2026-13"), (None, None))
        self.assertEqual(parse_date_range("2026-02-30..2026-03-01"), (None, None))

    def test_classify_explicit_zero_match(self) -> None:
        out = classify_variance(0.0, 0.0)
        self.assertEqual(out["result"], ReconciliationResult.MATCH.value)
        self.assertEqual(out.get("delta"), 0.0)

    def test_classify_isclose_match(self) -> None:
        # Cent-exact MATCH after Decimal quantize; sub-cent noise collapses to equal
        out = classify_variance(100.0, 100.001)
        self.assertEqual(out["result"], ReconciliationResult.MATCH.value)
        near = classify_variance(100.0, 99.99)
        self.assertEqual(
            near["result"], ReconciliationResult.VARIANCE_WITHIN_TOLERANCE.value
        )

    def test_classify_within_and_exceeds(self) -> None:
        within = classify_variance(100.0, 98.0)
        self.assertEqual(within["result"], ReconciliationResult.VARIANCE_WITHIN_TOLERANCE.value)
        self.assertFalse(within["thresholdViolated"])

        match = classify_variance(100.0, 100.0)
        self.assertEqual(match["result"], ReconciliationResult.MATCH.value)

        exceeds = classify_variance(100.0, 50.0)
        self.assertEqual(exceeds["result"], ReconciliationResult.VARIANCE_EXCEEDS_THRESHOLD.value)
        self.assertTrue(exceeds["thresholdViolated"])

    def test_sql_has_no_fstring_interpolation(self) -> None:
        import inspect

        import softdent_visual_ledger_recon as mod

        src = inspect.getsource(mod.sum_ledger_code2_payments)
        self.assertNotIn('f"""', src)
        self.assertNotIn("f'", src)
        self.assertNotIn("TRIM(procedure)", src)
        self.assertIn("procedure IN (", src)

    def test_triggers_gold_ingest_never_true(self) -> None:
        import softdent_visual_ledger_recon as mod

        src = Path(mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn('triggersGoldIngest": True', src)
        self.assertNotIn("triggersGoldIngest': True", src)

    def test_scope_mismatch_flag(self) -> None:
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
                    VALUES ('1','2026-06-10','2',1,0,0,0,0,0,50,0)
                    """
                )
                conn.commit()
            finally:
                conn.close()
            append_print_preview_audit(
                {
                    "reportType": "InsuranceIncome",
                    "dateRange": "2026-06-01..2026-07-15",
                    "lastPageAggregateTotal": 50.0,
                    "pageCount": 2,
                    "operatorId": "test",
                },
                dest=dest,
            )
            recon = reconcile_visual_vs_ledger(period="2026-06", dest=dest, db_path=db)
            self.assertTrue(recon.get("scopeMismatch"))
            self.assertFalse(recon.get("triggersGoldIngest"))

    def test_widget_returns_without_nameerror(self) -> None:
        w = visual_ledger_recon_widget()
        self.assertTrue(w.get("ok"))
        self.assertIn("result", w)
        self.assertEqual(w.get("packageBuildId"), "hal-10595")
        self.assertFalse(w.get("triggersGoldIngest"))

    def test_null_visual_never_treated_as_zero(self) -> None:
        out = classify_variance(None, 0.0)
        self.assertEqual(out["result"], ReconciliationResult.INSUFFICIENT_VISUAL.value)
        self.assertIsNone(out.get("delta"))
        # Must not invent a $0 visual comparison
        self.assertNotEqual(out["result"], ReconciliationResult.MATCH.value)

        halt = classify_variance(None, None)
        self.assertIn(
            halt["result"],
            {
                ReconciliationResult.INSUFFICIENT_VISUAL.value,
                ReconciliationResult.HONESTY_HALT.value,
            },
        )

    def test_null_ledger_insufficient(self) -> None:
        out = classify_variance(100.0, None)
        self.assertEqual(out["result"], ReconciliationResult.INSUFFICIENT_LEDGER.value)

    def test_end_to_end_temp_db_and_audit(self) -> None:
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
                        account_num TEXT,
                        service_date TEXT,
                        procedure TEXT,
                        row_number INTEGER,
                        prod REAL, charges REAL, prod_adj REAL, pay_adj REAL,
                        cash REAL, "check" REAL, credit REAL,
                        period_start TEXT, period_end TEXT, source_file TEXT
                    )
                    """
                )
                # Two code-2 insurance payments totaling 98.00
                conn.execute(
                    """
                    INSERT INTO sd_account_transactions
                    (account_num, service_date, procedure, row_number,
                     prod, charges, prod_adj, pay_adj, cash, "check", credit)
                    VALUES ('1','2026-06-10','2',1,0,0,0,0,0,50,0)
                    """
                )
                conn.execute(
                    """
                    INSERT INTO sd_account_transactions
                    (account_num, service_date, procedure, row_number,
                     prod, charges, prod_adj, pay_adj, cash, "check", credit)
                    VALUES ('2','2026-06-15','2',2,0,0,0,0,0,48,0)
                    """
                )
                conn.commit()
            finally:
                conn.close()

            append_print_preview_audit(
                {
                    "reportType": "InsuranceIncome",
                    "dateRange": "2026-06-01..2026-06-30",
                    "lastPageAggregateTotal": 100.0,
                    "pageCount": 3,
                    "operatorId": "test",
                },
                dest=dest,
            )

            ledger = sum_ledger_code2_payments(
                period_start="2026-06-01",
                period_end="2026-06-30",
                db_path=db,
            )
            self.assertEqual(ledger.get("ledgerTotal"), 98.0)

            recon = reconcile_visual_vs_ledger(period="2026-06", dest=dest, db_path=db)
            self.assertEqual(recon.get("visualTotal"), 100.0)
            self.assertEqual(recon.get("ledgerTotal"), 98.0)
            cmp_ = recon["comparison"]
            self.assertEqual(
                cmp_["result"], ReconciliationResult.VARIANCE_WITHIN_TOLERANCE.value
            )
            self.assertFalse(cmp_["thresholdViolated"])
            self.assertFalse(recon.get("triggersGoldIngest"))
            self.assertEqual(recon.get("paymentLines"), 0)

            # Exceeding variance
            append_print_preview_audit(
                {
                    "reportType": "InsuranceIncome",
                    "dateRange": "2026-06-01..2026-06-30",
                    "lastPageAggregateTotal": 200.0,
                    "pageCount": 3,
                    "operatorId": "test",
                },
                dest=dest,
            )
            recon2 = reconcile_visual_vs_ledger(period="2026-06", dest=dest, db_path=db)
            self.assertTrue(recon2["comparison"]["thresholdViolated"])

            run = run_ops_10592_visual_ledger_recon(period="2026-06", dest=dest, db_path=db)
            self.assertTrue(run.get("ok"))
            self.assertTrue(Path(run["jsonPath"]).is_file())

    def test_widget_and_reply(self) -> None:
        w = visual_ledger_recon_widget()
        self.assertEqual(w.get("packageBuildId"), "hal-10595")
        self.assertTrue(w.get("emptyIsNotZero"))
        self.assertFalse(w.get("triggersGoldIngest"))
        text = format_visual_ledger_recon_reply(
            {
                "period": "2026-06",
                "visualDisplay": "—",
                "ledgerDisplay": "—",
                "gapCode": "GOLD_CSV_MISSING",
                "paymentLines": 0,
                "comparison": {"result": "INSUFFICIENT_VISUAL", "delta": None, "thresholdViolated": False},
            }
        )
        self.assertIn("HAL-10595", text)
        self.assertIn("empty != $0", text)


if __name__ == "__main__":
    unittest.main()
