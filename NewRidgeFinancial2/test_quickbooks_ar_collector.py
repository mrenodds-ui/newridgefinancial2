import unittest

from quickbooks_ar_collector import build_quickbooks_ar_rows_from_sdk


class QuickbooksArCollectorTests(unittest.TestCase):
    def test_builds_rows_from_aging_list(self):
        payload = {
            "accounts_receivable": 17250,
            "ar_aging": [
                {"bucket": "0-30", "balance": 12500},
                {"bucket": "31-60", "balance": 3200},
            ],
        }
        rows = build_quickbooks_ar_rows_from_sdk(payload)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["Bucket"], "0-30")
        self.assertEqual(float(rows[0]["Balance"]), 12500.0)

    def test_builds_total_row_when_only_total_present(self):
        rows = build_quickbooks_ar_rows_from_sdk({"accounts_receivable": 9000})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Bucket"], "Total A/R")

    def test_empty_when_no_ar_fields(self):
        self.assertEqual(build_quickbooks_ar_rows_from_sdk({"total_income": 1}), [])


if __name__ == "__main__":
    unittest.main()
