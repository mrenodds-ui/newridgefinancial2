#!/usr/bin/env python3
"""HAL-10603 — Run honesty CI gate (null → $0.00 must fail the build).

Usage:
  python scripts/run_honesty_ci_gate.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NR2 = REPO / "NewRidgeFinancial2"
INTEGRATION = REPO / "tests" / "integration"
sys.path.insert(0, str(NR2))
sys.path.insert(0, str(INTEGRATION))


def main() -> int:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromName("test_hal10603_honesty_ci"))
    suite.addTests(loader.loadTestsFromName("test_hon_001_empty_not_zero_hal10591"))
    suite.addTests(loader.discover(str(INTEGRATION), pattern="test_widget_regression.py"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
