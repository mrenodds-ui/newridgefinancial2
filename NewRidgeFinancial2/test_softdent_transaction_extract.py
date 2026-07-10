"""Tests for SoftDent full transaction / register / operatory extract (Moonshot pack)."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from softdent_odbc_extract import _is_adjustment, _is_payment, _normalize_softdent_code
from softdent_transaction_extract import (
    extract_all_transactions,
    load_operatory_schedule,
    load_transactions_jsonl,
)


class SoftDentCodeNormalizeTests(unittest.TestCase):
    def test_normalize_decimal_codes(self) -> None:
        self.assertEqual(_normalize_softdent_code("2.00"), "2")
        self.assertEqual(_normalize_softdent_code("51.0"), "51")
        self.assertEqual(_normalize_softdent_code("1110"), "1110")

    def test_payment_and_adjustment_codes(self) -> None:
        self.assertTrue(_is_payment("2", ""))
        self.assertTrue(_is_payment("2.00", ""))
        self.assertTrue(_is_payment("11", "Patient payment"))
        self.assertFalse(_is_payment("51", "write-off"))
        self.assertTrue(_is_adjustment("51", ""))
        self.assertTrue(_is_adjustment("52.00", ""))
        self.assertTrue(_is_adjustment("", "Insurance write-off"))


class SoftDentTransactionExtractTests(unittest.TestCase):
    def test_load_normalized_jsonl_and_persist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exports = root / "exports"
            exports.mkdir()
            db_path = root / "analytics.sqlite3"
            sqlite3.connect(db_path).close()

            lines = [
                {
                    "dataset_name": "transactions_for_period",
                    "source_file": "tx.csv",
                    "row_number": 1,
                    "normalized": {
                        "source_summary_type": "transactions_for_period_totals",
                        "gross_production": 1000,
                    },
                },
                {
                    "dataset_name": "transactions_for_period",
                    "source_file": "tx.csv",
                    "row_number": 2,
                    "normalized": {
                        "transaction_date": "2026-07-01",
                        "posting_date": "2026-07-01",
                        "service_date": "2026-07-01",
                        "transaction_code": "1110",
                        "transaction_description": "Prophy",
                        "transaction_type": "transaction",
                        "amount": 120.0,
                        "provider_id": "1",
                        "patient_id": "1001",
                    },
                },
                {
                    "dataset_name": "transactions_for_period",
                    "source_file": "tx.csv",
                    "row_number": 3,
                    "normalized": {
                        "transaction_date": "2026-07-01",
                        "posting_date": "2026-07-01",
                        "transaction_code": "2",
                        "transaction_description": "Insurance Check",
                        "transaction_type": "payment",
                        "amount": 85.0,
                        "patient_id": "1001",
                    },
                },
                {
                    "dataset_name": "transactions_for_period",
                    "source_file": "tx.csv",
                    "row_number": 4,
                    "normalized": {
                        "transaction_date": "2026-07-01",
                        "posting_date": "2026-07-01",
                        "transaction_code": "51",
                        "transaction_description": "Write-Off",
                        "transaction_type": "adjustment",
                        "amount": 40.0,
                        "patient_id": "1001",
                    },
                },
            ]
            (exports / "transactions_for_period.jsonl").write_text(
                "\n".join(json.dumps(row) for row in lines) + "\n",
                encoding="utf-8",
            )
            (exports / "register_for_period.jsonl").write_text(
                json.dumps(
                    {
                        "dataset_name": "register_for_period",
                        "source_file": "reg.csv",
                        "row_number": 1,
                        "raw_row": ["Collections", "", "$1,234.56", ""],
                        "normalized": {"adjustments_to_prod": "Collections"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (exports / "operatory_schedule.json").write_text(
                json.dumps(
                    {
                        "operatoryChairs": [
                            {
                                "name": "1",
                                "slots": [
                                    {
                                        "time": "2026-07-10",
                                        "patient": "Jane Doe",
                                        "procedure": "checked-in",
                                        "tone": "ok",
                                    }
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            txs = load_transactions_jsonl(exports / "transactions_for_period.jsonl")
            self.assertEqual(len(txs), 3)

            with unittest.mock.patch(
                "softdent_transaction_extract.resolve_exports_dir", return_value=exports
            ), unittest.mock.patch(
                "softdent_transaction_extract.resolve_analytics_db", return_value=db_path
            ), unittest.mock.patch(
                "softdent_transaction_extract.load_operatory_schedule",
                return_value=load_operatory_schedule(exports / "operatory_schedule.json"),
            ):
                result = extract_all_transactions(db_path=db_path, force=True)

            self.assertTrue(result["ok"], result)
            self.assertEqual(result["transactions"], 3)
            self.assertGreaterEqual(result["register"], 1)
            self.assertGreaterEqual(result["operatory"], 1)
            self.assertGreaterEqual((result.get("verification") or {}).get("parity_ratio") or 0, 0.9)

            conn = sqlite3.connect(db_path)
            try:
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM sd_transactions_full").fetchone()[0], 3
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM sd_transactions_full WHERE transaction_type='payment'"
                    ).fetchone()[0],
                    1,
                )
                self.assertGreaterEqual(
                    conn.execute("SELECT COUNT(*) FROM sd_payments").fetchone()[0], 1
                )
                self.assertGreaterEqual(
                    conn.execute("SELECT COUNT(*) FROM sd_adjustments").fetchone()[0], 1
                )
                self.assertGreaterEqual(
                    conn.execute("SELECT COUNT(*) FROM sd_operatory_schedule").fetchone()[0], 1
                )
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
