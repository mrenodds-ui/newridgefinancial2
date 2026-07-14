"""Moonshot TXN ledger surface (hal-10576)."""

from __future__ import annotations

import unittest
from pathlib import Path

from apex_backend import BUILD_ID
from apex_better_backend_widgets_pack import build_transaction_ledger_table
from softdent_transaction_extract import load_txn_jsonl, query_account_transactions


class TxnLedgerSurfaceTests(unittest.TestCase):
    def test_build_id(self) -> None:
        self.assertEqual(BUILD_ID, "hal-10576")

    def test_load_txn_jsonl_alias(self) -> None:
        rows = load_txn_jsonl()
        self.assertIsInstance(rows, list)

    def test_ledger_widget_empty_or_ok(self) -> None:
        w = build_transaction_ledger_table({}, page="softdent", limit=10)
        self.assertEqual(w["type"], "data-table")
        self.assertEqual(w["id"], "softdent-transaction-ledger")
        self.assertEqual(w["columns"][0], "Date")
        self.assertIn(w["status"], {"ok", "empty"})

    def test_ledger_unknown_account_empty(self) -> None:
        w = build_transaction_ledger_table(
            {},
            page="softdent",
            account_num="99999999",
            limit=10,
        )
        # If no JSONL at all, also empty — either way never invent rows
        self.assertEqual(w["status"], "empty")
        self.assertTrue(w.get("emptyState") or w["status"] == "empty")
        self.assertEqual(w["rows"], [])

    def test_donna_account_27002_when_jsonl_present(self) -> None:
        parsed = Path(r"C:\SoftDentFinancialExports\tx_parsed")
        if not parsed.is_dir() or not any(parsed.glob("*.jsonl")):
            self.skipTest("tx_parsed JSONL not present")
        result = query_account_transactions(
            account_num="27002",
            patient_name="Donna",
            date_range="2026-02",
            limit=50,
        )
        self.assertTrue(result.get("ok"))
        self.assertEqual(int(result.get("matchCount") or 0), 5)
        w = build_transaction_ledger_table(
            {},
            page="softdent",
            account_num="27002",
            patient_name="Donna",
            date_range="2026-02",
            limit=50,
        )
        self.assertEqual(w["status"], "ok")
        self.assertEqual(len(w["rows"]), 5)
        self.assertFalse(w.get("emptyState"))
        # Honesty: Amount null stays null (never forced to 0)
        for row in w["rows"]:
            amt = row.get("Amount")
            if amt is not None:
                self.assertIsInstance(amt, (int, float))
            self.assertNotEqual(amt, "0.00")

    def test_hal_policy_donna_february_consistent(self) -> None:
        from nr2_hal_gateway import try_local_policy_reply

        hit = try_local_policy_reply(
            "What are Donna Nickel's February 2026 transactions?"
        )
        self.assertIsNotNone(hit)
        self.assertEqual(hit.get("intent"), "policy:softdent-account-tx-ledger")
        text = hit.get("text") or ""
        self.assertIn("27002", text)
        self.assertIn("2026-02-18", text)

if __name__ == "__main__":
    unittest.main()
