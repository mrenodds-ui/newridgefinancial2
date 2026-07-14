"""Year-chunk SoftDent account-tx ingest (TXNALL + TXN2017H2..YTD)."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from softdent_transaction_extract import (
    ingest_account_transactions_year_chunks,
    parse_account_transactions_xls,
    resolve_txn_export_path,
    upsert_account_transactions_jsonl,
    write_account_transactions_jsonl,
)

LIVE_2018 = Path(r"C:\SoftDentReportExports\TXN2018.xls")
LIVE_MANIFEST = Path(r"C:\SoftDentFinancialExports\softdent_account_tx_year_chunks.json")


class YearChunkIngestTests(unittest.TestCase):
    @unittest.skipUnless(LIVE_2018.is_file(), "TXN2018 export not present")
    def test_parse_csv_disguised_as_xls(self) -> None:
        parsed = parse_account_transactions_xls(LIVE_2018)
        self.assertTrue(parsed.get("ok"), msg=str(parsed.get("warnings")))
        self.assertGreater(int(parsed.get("recordCount") or 0), 10_000)
        # Manifest expected 18891 for 2018
        self.assertAlmostEqual(int(parsed["recordCount"]), 18891, delta=50)
        rec = (parsed.get("records") or [None])[0]
        self.assertIsNotNone(rec)
        assert rec is not None
        self.assertTrue(str(rec.get("date") or "").startswith("2018-"))
        self.assertTrue(rec.get("account_num"))

    @unittest.skipUnless(LIVE_2018.is_file(), "TXN2018 export not present")
    def test_year_chunk_upsert_idempotent_temp_db(self) -> None:
        parsed = parse_account_transactions_xls(LIVE_2018)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            written = write_account_transactions_jsonl(
                parsed, out_dir=root / "parsed", source_path=LIVE_2018
            )
            db = root / "analytics.db"
            first = upsert_account_transactions_jsonl(written["path"], db_path=db)
            second = upsert_account_transactions_jsonl(written["path"], db_path=db)
            self.assertTrue(first.get("ok"))
            self.assertTrue(second.get("ok"))
            self.assertEqual(first.get("dbCount"), second.get("dbCount"))
            self.assertEqual(int(first.get("dbCount") or 0), int(parsed["recordCount"]))

    def test_resolve_txn_export_path_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(resolve_txn_export_path("TXN9999", Path(tmp)))

    @unittest.skipUnless(
        LIVE_MANIFEST.is_file() and resolve_txn_export_path("TXN2026YTD") is not None,
        "year-chunk exports / manifest not present",
    )
    def test_ingest_year_chunks_against_live_optional(self) -> None:
        # Full live ingest is expensive; this test only runs when explicitly enabled.
        import os

        if os.environ.get("SOFTDENT_YEAR_CHUNK_INGEST_TEST") != "1":
            self.skipTest("set SOFTDENT_YEAR_CHUNK_INGEST_TEST=1 to run full live ingest")
        result = ingest_account_transactions_year_chunks()
        self.assertTrue(result.get("ok"), msg=json.dumps(result, indent=2)[:2000])
        self.assertGreater(int(result.get("dbTotal") or 0), 100_000)
        self.assertTrue(result.get("account_tx_multi_year_available"))


if __name__ == "__main__":
    unittest.main()
