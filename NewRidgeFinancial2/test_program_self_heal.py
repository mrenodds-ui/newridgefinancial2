"""Tests for program_self_heal."""

from __future__ import annotations

import unittest

from program_self_heal import run_program_self_heal


class ProgramSelfHealTests(unittest.TestCase):
    def test_documents_only_self_heal_returns_report(self) -> None:
        report = run_program_self_heal(pull_imports=False, reason="test")
        self.assertIn("status", report)
        self.assertIn("steps", report)
        self.assertTrue(isinstance(report["steps"], list))
        self.assertGreaterEqual(len(report["steps"]), 2)
        self.assertIn("health", report)


if __name__ == "__main__":
    unittest.main()
