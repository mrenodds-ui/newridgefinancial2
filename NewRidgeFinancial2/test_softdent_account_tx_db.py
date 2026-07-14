"""Moonshot SoftDent account-tx DB (sd_account_transactions)."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from softdent_transaction_extract import (
    ingest_account_transactions_xls,
    query_account_transactions,
    upsert_account_transactions_jsonl,
)

LIVE_TXN = Path(r"C:\SoftDentReportExports\TXN260201.xls")
LIVE_JSONL = Path(r"C:\SoftDentFinancialExports\tx_parsed\TXN260201.jsonl")


class AccountTxDbTests(unittest.TestCase):
    @unittest.skipUnless(LIVE_JSONL.is_file() or LIVE_TXN.is_file(), "TXN export not present")
    def test_upsert_and_query_donna_from_db(self):
        # Use a temp analytics DB so live year-chunk ledger is not polluted by TXN260201.
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "analytics.db"
            if LIVE_TXN.is_file():
                ingest = ingest_account_transactions_xls(LIVE_TXN, db_path=db)
                self.assertTrue(ingest.get("ok"), msg=str(ingest))
                self.assertEqual(ingest.get("recordCount"), 1716)
                db_info = ingest.get("db") or {}
            else:
                db_info = upsert_account_transactions_jsonl(LIVE_JSONL, db_path=db)
                self.assertTrue(db_info.get("ok"), msg=str(db_info))

            self.assertEqual(int(db_info.get("dbCount") or 0), 1716)
            self.assertEqual(int(db_info.get("donna27002Count") or 0), 5)

            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                n = conn.execute("SELECT COUNT(*) FROM sd_account_transactions").fetchone()[0]
                self.assertEqual(int(n), 1716)
                nulls = conn.execute(
                    "SELECT COUNT(*) FROM sd_account_transactions WHERE amount IS NULL"
                ).fetchone()[0]
                self.assertGreater(int(nulls), 0)
            finally:
                conn.close()

            q = query_account_transactions(
                account_num="27002",
                patient_name="Donna",
                date_range="2026-02",
                prefer_db=True,
                db_path=db,
            )
            self.assertTrue(q.get("ok"))
            self.assertEqual(q.get("source"), "sd_account_transactions")
            self.assertEqual(q.get("matchCount"), 5)

    @unittest.skipUnless(LIVE_JSONL.is_file(), "TXN JSONL not present")
    def test_upsert_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "analytics.db"
            first = upsert_account_transactions_jsonl(LIVE_JSONL, db_path=db)
            second = upsert_account_transactions_jsonl(LIVE_JSONL, db_path=db)
            self.assertTrue(first.get("ok"))
            self.assertTrue(second.get("ok"))
            self.assertEqual(first.get("dbCount"), second.get("dbCount"))
            self.assertEqual(first.get("dbCount"), 1716)

    def test_temp_db_schema_and_null_money(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test_analytics.db"
            # Minimal JSONL
            jsonl = Path(tmp) / "TXNTEST.jsonl"
            jsonl.write_text(
                "\n".join(
                    [
                        json_meta(),
                        json_row(1, "27002", "Nickel, Donna", "2026-02-18", 137.0),
                        json_row(2, "27002", "Nickel, Donna", "2026-02-18", None),
                    ]
                ),
                encoding="utf-8",
            )
            result = upsert_account_transactions_jsonl(jsonl, db_path=db)
            self.assertTrue(result.get("ok"), msg=str(result))
            self.assertEqual(result.get("dbCount"), 2)
            conn = sqlite3.connect(str(db))
            try:
                null_amt = conn.execute(
                    "SELECT COUNT(*) FROM sd_account_transactions WHERE amount IS NULL"
                ).fetchone()[0]
                self.assertEqual(int(null_amt), 1)
            finally:
                conn.close()
            q = query_account_transactions(
                account_num="27002",
                db_path=db,
                prefer_db=True,
            )
            self.assertEqual(q.get("source"), "sd_account_transactions")
            self.assertEqual(q.get("matchCount"), 2)


def json_meta() -> str:
    import json

    return json.dumps(
        {
            "_meta": True,
            "sourcePath": r"C:\SoftDentReportExports\TXNTEST.xls",
            "rowCount": 3,
            "recordCount": 2,
            "periodHint": "2026-02-01:2026-02-28",
        }
    )


def json_row(
    row_number: int,
    account: str,
    name: str,
    date: str,
    amount: float | None,
) -> str:
    import json

    return json.dumps(
        {
            "date": date,
            "account_num": account,
            "patient_name": name,
            "provider": "1",
            "procedure": "1110",
            "amount": amount,
            "note_flag": "A",
            "row_number": row_number,
            "source_file": "TXNTEST.xls",
            "prod": amount,
            "charges": None,
            "prod_adj": None,
            "cash": None,
            "check": None,
            "credit": None,
            "pay_adj": None,
        }
    )


if __name__ == "__main__":
    unittest.main()
