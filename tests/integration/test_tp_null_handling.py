"""Integration honesty gate — TP null handling (HAL-10603).

Moonshot path: tests/integration/test_tp_null_handling.py
Delegates to NewRidgeFinancial2 unittest suite (repo CI uses unittest discover).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

NR2 = Path(__file__).resolve().parents[2] / "NewRidgeFinancial2"
if str(NR2) not in sys.path:
    sys.path.insert(0, str(NR2))

from test_hal10603_honesty_ci import (  # noqa: E402
    HonestyCiGateHal10603Tests,
    assert_no_fake_zero_dollars,
)

# Re-export for pytest/unittest discovery from repo root.
__all__ = ["HonestyCiGateHal10603Tests", "assert_no_fake_zero_dollars", "TpNullHandlingTests"]


class TpNullHandlingTests(HonestyCiGateHal10603Tests):
    """Alias class name for Moonshot consult path."""

    pass


if __name__ == "__main__":
    unittest.main()
