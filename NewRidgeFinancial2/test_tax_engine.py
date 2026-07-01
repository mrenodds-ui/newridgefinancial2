"""Tests for tax_engine.py planning snapshot."""

from __future__ import annotations

import unittest

from tax_engine import build_tax_plan, build_tax_plan_from_bundle, employer_fica


class TaxEngineTests(unittest.TestCase):
    def test_employer_fica_caps_at_wage_base(self) -> None:
        self.assertEqual(employer_fica(100_000), 7650)
        self.assertEqual(employer_fica(500_000), employer_fica(174_900))

    def test_build_tax_plan_with_book_income(self) -> None:
        plan = build_tax_plan(book_net_income=886_559, ebitda_add_backs=42_000, period_label="Jun 2025")
        self.assertTrue(plan["hasBookData"])
        self.assertGreater(plan["k1Ordinary"], plan["bookNetIncome"])
        self.assertGreater(plan["totalOwnerTaxEstimate"], 0)
        self.assertEqual(len(plan["compScenarios"]), 3)
        self.assertEqual(len(plan["bridgeLines"]), 8)

    def test_build_from_qb_bundle(self) -> None:
        bundle = {
            "quickbooks": {
                "profitAndLoss": {
                    "rows": [{"Period": "2026-06", "NetIncome": "57093.75"}],
                }
            }
        }
        plan = build_tax_plan_from_bundle(bundle)
        self.assertEqual(plan["bookNetIncome"], 57094)
        self.assertGreater(plan["federalTaxEstimate"], 0)


if __name__ == "__main__":
    unittest.main()
