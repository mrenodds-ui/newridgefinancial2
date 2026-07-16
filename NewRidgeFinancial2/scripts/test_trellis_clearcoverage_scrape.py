"""Unit tests for ClearCoverage money/pct/service text parsers (no live Trellis)."""
from __future__ import annotations

import unittest

from trellis_clearcoverage_scrape import (
    parse_money_pair,
    parse_pct,
    _scrape_services_from_text,
)


class TestClearCoverageParsers(unittest.TestCase):
    def test_money_pair(self) -> None:
        self.assertEqual(parse_money_pair("$50 / $50"), (50.0, 50.0))
        self.assertEqual(parse_money_pair("$1,500 / $1,500"), (1500.0, 1500.0))
        self.assertEqual(parse_money_pair("Not Provided"), (None, None))
        self.assertEqual(parse_money_pair(""), (None, None))
        self.assertEqual(parse_money_pair(" / "), (None, None))

    def test_pct(self) -> None:
        self.assertEqual(parse_pct("100%"), 100)
        self.assertEqual(parse_pct("80 %"), 80)
        self.assertIsNone(parse_pct("Not Provided"))
        self.assertIsNone(parse_pct(""))

    def test_service_block(self) -> None:
        block = """
Preventive
Exams
Frequency
2 treatments per calendar year
Age Limit
Not Provided
Coinsurance
100%
ADA Codes
D0120
D0150 100%
Prophylaxis
Frequency
2 treatments per calendar year
Age Limit
Not Provided
Coinsurance
100%
ADA Codes
D1110
"""
        svcs = _scrape_services_from_text(block)
        names = [s["name"] for s in svcs]
        self.assertIn("Exams", names)
        self.assertIn("Prophylaxis", names)
        exams = next(s for s in svcs if s["name"] == "Exams")
        self.assertEqual(exams["coinsurancePct"], 100)
        self.assertEqual(exams["frequency"], "2 treatments per calendar year")
        codes = {a["code"] for a in exams["adaCodes"]}
        self.assertIn("D0120", codes)
        self.assertIn("D0150", codes)


if __name__ == "__main__":
    unittest.main()
