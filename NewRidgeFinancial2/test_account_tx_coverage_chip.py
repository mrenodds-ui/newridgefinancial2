"""Account-tx ledger coverage chip (multi-year HAL visibility)."""

from __future__ import annotations

import unittest

from apex_better_backend_widgets_pack import (
    build_account_tx_ledger_coverage_chip,
    build_transaction_ledger_table,
)
from softdent_transaction_extract import account_tx_ledger_coverage


class AccountTxCoverageChipTests(unittest.TestCase):
    def test_coverage_chip_live(self) -> None:
        cov = account_tx_ledger_coverage()
        if int(cov.get("dbTotal") or 0) < 100_000:
            self.skipTest("year-chunk DB not loaded")
        chip = build_account_tx_ledger_coverage_chip({}, page="softdent")
        self.assertEqual(chip.get("id"), "softdent-account-tx-coverage")
        self.assertEqual(chip.get("type"), "status")
        self.assertEqual(chip.get("status"), "ok")
        self.assertTrue(chip.get("account_tx_multi_year_available"))
        self.assertEqual(int(chip.get("dbTotal") or 0), int(cov["dbTotal"]))
        msg = chip.get("message") or ""
        self.assertIn("account transactions", msg)
        self.assertIn("1996", msg)
        self.assertIn("2026", msg)
        # Honesty: no invented dollar rollup in message
        self.assertNotIn("$", msg)
        hint = chip.get("hint") or ""
        self.assertIn("27002", hint)
        self.assertIn("empty", hint.lower())

    def test_ledger_empty_filter_no_zero_dollars(self) -> None:
        w = build_transaction_ledger_table(
            {},
            page="softdent",
            account_num="99999999",
            limit=10,
        )
        self.assertEqual(w.get("status"), "empty")
        self.assertEqual(w.get("emptyMessage"), "No transactions found")
        self.assertEqual(w.get("rows"), [])
        self.assertNotIn("$0", str(w.get("emptyMessage") or ""))

    def test_office_manager_chip_id(self) -> None:
        chip = build_account_tx_ledger_coverage_chip({}, page="office-manager")
        self.assertEqual(chip.get("id"), "office-manager-account-tx-coverage")


if __name__ == "__main__":
    unittest.main()
