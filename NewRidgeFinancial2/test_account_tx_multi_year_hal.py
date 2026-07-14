"""HAL multi-year account-tx ledger wiring after year-chunk ingest."""

from __future__ import annotations

import unittest

from nr2_hal_gateway import _extract_account_tx_query_filters, try_local_policy_reply
from softdent_transaction_extract import (
    _parse_date_range,
    account_tx_ledger_coverage,
    format_account_transactions_hal_reply,
    query_account_transactions,
)


class MultiYearAccountTxHalTests(unittest.TestCase):
    def test_parse_year_and_span(self) -> None:
        self.assertEqual(_parse_date_range("2018"), ("2018-01-01", "2018-12-31"))
        self.assertEqual(_parse_date_range("2018:2019"), ("2018-01-01", "2019-12-31"))
        self.assertEqual(_parse_date_range("2026-02")[0], "2026-02-01")

    def test_extract_filters_year_and_history(self) -> None:
        f1 = _extract_account_tx_query_filters(
            "Show account 27002 transactions in 2018"
        )
        self.assertIsNotNone(f1)
        assert f1 is not None
        self.assertEqual(f1.get("account_num"), "27002")
        self.assertEqual(f1.get("date_range"), "2018")
        self.assertNotIn("patient_name", f1)

        f2 = _extract_account_tx_query_filters(
            "Account history for account 7702 from 2018 to 2019"
        )
        self.assertIsNotNone(f2)
        assert f2 is not None
        self.assertEqual(f2.get("account_num"), "7702")
        self.assertEqual(f2.get("date_range"), "2018:2019")

    def test_coverage_live_when_db_present(self) -> None:
        cov = account_tx_ledger_coverage()
        if int(cov.get("dbTotal") or 0) < 100_000:
            self.skipTest("year-chunk DB not loaded")
        self.assertTrue(cov.get("account_tx_multi_year_available"))
        self.assertTrue(str(cov.get("serviceDateMin") or "").startswith("1996"))
        self.assertTrue(str(cov.get("serviceDateMax") or "").startswith("2026"))

    def test_donna_feb_and_hal_reply_coverage(self) -> None:
        result = query_account_transactions(
            account_num="27002",
            patient_name="Donna",
            date_range="2026-02",
            prefer_db=True,
            limit=50,
        )
        if not result.get("ok") or int(result.get("dbTotal") or 0) < 100_000:
            self.skipTest("year-chunk DB not loaded")
        self.assertEqual(result.get("source"), "sd_account_transactions")
        self.assertEqual(int(result.get("matchCount") or 0), 5)
        self.assertTrue(result.get("account_tx_multi_year_available"))
        text = format_account_transactions_hal_reply(result)
        self.assertIn("sd_account_transactions", text)
        self.assertIn("account_tx_multi_year_available=true", text)
        self.assertIn("db_total=", text)
        self.assertIn("available_range=", text)
        self.assertIn("27002", text)

    def test_hal_policy_2018_account_query(self) -> None:
        cov = account_tx_ledger_coverage()
        if int(cov.get("dbTotal") or 0) < 100_000:
            self.skipTest("year-chunk DB not loaded")
        hit = try_local_policy_reply("Show account 27002 transactions in 2018")
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit.get("intent"), "policy:softdent-account-tx-ledger")
        text = hit.get("text") or ""
        self.assertIn("sd_account_transactions", text)
        self.assertIn("account_tx_multi_year_available=true", text)
        # Should not claim empty when 2018 ledger exists for this account (or honest empty)
        self.assertIn("empty != $0", text)

    def test_hal_policy_donna_still_works(self) -> None:
        hit = try_local_policy_reply(
            "What are Donna Nickel's February 2026 transactions?"
        )
        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit.get("intent"), "policy:softdent-account-tx-ledger")
        text = hit.get("text") or ""
        self.assertIn("27002", text)
        self.assertIn("2026-02-18", text)


if __name__ == "__main__":
    unittest.main()
