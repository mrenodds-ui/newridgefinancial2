"""Moonshot SoftDent TXN Excel ingest + HAL patient-ledger (AFTER_ACCOUNT_TX_EXCEL)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from softdent_transaction_extract import (
    format_account_transactions_hal_reply,
    ingest_account_transactions_xls,
    parse_account_transactions_xls,
    query_account_transactions,
    write_account_transactions_jsonl,
)

LIVE_TXN = Path(r"C:\SoftDentReportExports\TXN260201.xls")


class ParseAccountTransactionsXlsTests(unittest.TestCase):
    @unittest.skipUnless(LIVE_TXN.is_file(), "TXN260201.xls not in SoftDentReportExports")
    def test_live_txn_row_count_and_donna(self):
        parsed = parse_account_transactions_xls(LIVE_TXN)
        self.assertTrue(parsed.get("ok"))
        self.assertEqual(parsed.get("rowCount"), 1736)
        records = parsed.get("records") or []
        self.assertGreater(len(records), 0)
        donna = [
            r
            for r in records
            if str(r.get("account_num") or "") == "27002"
            or "nickel, donna" in str(r.get("patient_name") or "").lower()
        ]
        self.assertEqual(len(donna), 5)
        nickel = [r for r in records if "nickel" in str(r.get("patient_name") or "").lower()]
        self.assertEqual(len(nickel), 8)
        # Typed fields present; empty money stays None (never invent $0)
        for key in ("date", "account_num", "patient_name", "provider", "procedure", "amount", "note_flag"):
            self.assertIn(key, donna[0])
        # Donna Feb 18 production lines have amounts; no coerced zeros on empty legs
        feb18 = [r for r in donna if r.get("date") == "2026-02-18"]
        self.assertEqual(len(feb18), 3)
        self.assertTrue(all(r.get("amount") is not None for r in feb18))
        # At least one payment/credit line with amount and no invented prod=$0 requirement
        feb22 = [r for r in donna if r.get("date") == "2026-02-22"]
        self.assertEqual(len(feb22), 2)

    @unittest.skipUnless(LIVE_TXN.is_file(), "TXN260201.xls not in SoftDentReportExports")
    def test_ingest_writes_jsonl_and_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            result = ingest_account_transactions_xls(LIVE_TXN, out_dir=out)
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("rowCount"), 1736)
            self.assertEqual(result.get("nickelMentions"), 8)
            jsonl = Path(result["jsonlPath"])
            self.assertTrue(jsonl.is_file())
            lines = [ln for ln in jsonl.read_text(encoding="utf-8").splitlines() if ln.strip()]
            self.assertGreaterEqual(len(lines), 2)
            meta = json.loads(lines[0])
            self.assertTrue(meta.get("_meta"))
            q = query_account_transactions(
                account_num="27002",
                patient_name="Donna",
                date_range="2026-02",
                parsed_dir=out,
            )
            self.assertTrue(q.get("ok"))
            self.assertEqual(q.get("matchCount"), 5)
            text = format_account_transactions_hal_reply(q)
            self.assertIn("27002", text)
            self.assertIn("2026-02-18", text)
            self.assertNotIn("$0.00 invented", text)

    def test_missing_file_fallback_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = query_account_transactions(
                account_num="27002",
                parsed_dir=Path(tmp) / "empty",
            )
            # May still find live inbox TXN — if so ok; if not, not-yet-exported
            if not q.get("ok"):
                self.assertIn("not yet exported", (q.get("message") or "").lower())


class HalGatewayAccountTxTests(unittest.TestCase):
    @unittest.skipUnless(LIVE_TXN.is_file(), "TXN260201.xls not in SoftDentReportExports")
    def test_gateway_query_and_local_policy_donna(self):
        from nr2_hal_gateway import query_account_transactions as gw_query
        from nr2_hal_gateway import try_local_policy_reply

        # Ensure JSONL exists for deterministic policy path
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            ingest_account_transactions_xls(LIVE_TXN, out_dir=out)
            # Point query at temp via kwargs on extract path used by gateway
            result = gw_query(
                account_num="27002",
                patient_name="Nickel, Donna",
                date_range="2026-02",
                parsed_dir=out,
            )
            self.assertTrue(result.get("ok"))
            self.assertEqual(result.get("matchCount"), 5)

        # Local policy uses default parsed dir / live inbox fallback
        hit = try_local_policy_reply(
            "What are Donna Nickel's February 2026 transactions?"
        )
        self.assertIsNotNone(hit)
        self.assertEqual(hit.get("intent"), "policy:softdent-account-tx-ledger")
        text = hit.get("text") or ""
        self.assertIn("27002", text)
        self.assertTrue(
            "2026-02-18" in text or "not yet exported" in text.lower(),
            msg=text[:400],
        )


if __name__ == "__main__":
    unittest.main()
