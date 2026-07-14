"""Tests for gold money hardening (Decimal CSV parse + incomplete skip)."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from money_cents import to_money, to_money_from_csv
from softdent_gold_era_settlement_hal10608 import settlement_hydration_readiness_gate
from softdent_treatment_planning import (
    ensure_treatment_planning_schema,
    ingest_insurance_payment_csv,
    parse_money,
)


class GoldMoneyHardeningTests(unittest.TestCase):
    def test_parse_money_rejects_nan_inf(self) -> None:
        self.assertIsNone(parse_money(float("nan")))
        self.assertIsNone(parse_money(float("inf")))
        self.assertIsNone(parse_money(""))

    def test_parse_money_accounting_parens_and_csv_zero(self) -> None:
        self.assertEqual(parse_money("(12.34)"), -12.34)
        self.assertEqual(parse_money("0.00"), 0.0)
        self.assertEqual(to_money_from_csv("0.00"), Decimal("0.00"))
        # UI honesty path still treats ambiguous string zero as empty
        self.assertIsNone(to_money("0.00"))

    def test_ingest_skips_incomplete_gold_rows(self) -> None:
        csv_body = (
            "Insurance Company,Procedure Code,Paid Amount\n"
            "Delta Dental,D1110,45.00\n"
            ",D0120,10.00\n"  # missing InsCo
            "Aetna,,20.00\n"  # missing ADA
            "MetLife,D0274,\n"  # missing Paid
        )
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "a.db"
            pay = Path(tmp) / "insurance_payments_20260713.csv"
            pay.write_text(csv_body, encoding="utf-8")
            conn = sqlite3.connect(str(db))
            try:
                ensure_treatment_planning_schema(conn)
                n = ingest_insurance_payment_csv(pay, conn)
                self.assertEqual(n, 1)
                row = conn.execute(
                    "SELECT insurance_company, ada_code, paid_amount "
                    "FROM sd_insurance_payment_lines"
                ).fetchone()
                self.assertEqual(row[0], "Delta Dental")
                self.assertEqual(row[1], "D1110")
                self.assertEqual(row[2], 45.0)
                audit = conn.execute(
                    "SELECT rows_accepted, rows_skipped_incomplete "
                    "FROM sd_insurance_payment_ingest_audit"
                ).fetchone()
                self.assertEqual(audit[0], 1)
                self.assertEqual(audit[1], 3)
            finally:
                conn.close()

    def test_era_paid_gate_uses_decimal_not_float_litter(self) -> None:
        gate = settlement_hydration_readiness_gate(
            gold={"gapCode": "GOLD_CSV_MISSING", "paymentLines": 0},
            era={
                "gapCode": None,
                "fileCount": 0,
                "pending": False,
                "ingestedRowSample": 1,
                "latestTotalPaid": "0.00",
            },
        )
        self.assertFalse(gate.get("ready"))
        self.assertFalse(gate.get("eraReady"))


if __name__ == "__main__":
    unittest.main()
