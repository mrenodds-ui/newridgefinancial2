"""Static scan for risky SQL string interpolation in Python."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKIP = {"test_sql_parameterization.py", "program_source_grep.py"}


class SQLParameterizationTests(unittest.TestCase):
    def test_no_dynamic_execute_fstrings_in_core_modules(self) -> None:
        pattern = re.compile(r'execute\s*\(\s*f["\']')
        offenders: list[str] = []
        for path in ROOT.glob("*.py"):
            if path.name in SKIP:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), 1):
                if "execute(" in line and 'f"' in line:
                    if "PRAGMA" in line or "confidence_sql" in line or "review_sql" in line:
                        continue
                    offenders.append(f"{path.name}:{i}")
        self.assertEqual(offenders, [], f"parameterize SQL: {offenders[:10]}")


if __name__ == "__main__":
    unittest.main()
