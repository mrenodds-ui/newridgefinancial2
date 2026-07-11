"""Phase I0 validation — AI Orchestrator lane classification (no Ollama required)."""

from __future__ import annotations

import os
import unittest

from apex_orchestrator_pack import (
    classify_intent,
    orchestrate,
    orchestrator_enabled,
    orchestrator_status,
)


class OrchestratorPhaseI0Tests(unittest.TestCase):
    def test_flag_default_off(self):
        prev = os.environ.pop("NR2_AI_ORCHESTRATOR", None)
        try:
            self.assertFalse(orchestrator_enabled())
            st = orchestrator_status()
            self.assertFalse(st.get("enabled"))
            self.assertEqual(st.get("phase"), "S3")
        finally:
            if prev is not None:
                os.environ["NR2_AI_ORCHESTRATOR"] = prev

    def test_flag_on(self):
        prev = os.environ.get("NR2_AI_ORCHESTRATOR")
        os.environ["NR2_AI_ORCHESTRATOR"] = "1"
        try:
            self.assertTrue(orchestrator_enabled())
        finally:
            if prev is None:
                os.environ.pop("NR2_AI_ORCHESTRATOR", None)
            else:
                os.environ["NR2_AI_ORCHESTRATOR"] = prev

    def test_deep_routes_to_30b(self):
        cases = [
            "Run a monthly practice health audit",
            "Forecast collections for next quarter",
            "Cross-reference SoftDent production with QuickBooks expenses",
            "Compare SoftDent ledger with QB P&L and explain the gap",
            "Why did the production trend drop last month?",
            "Second opinion on this complex financial review",
        ]
        for q in cases:
            got = classify_intent(q)
            self.assertEqual(got.get("lane"), "escalate30b", q)
            self.assertEqual(got.get("reason"), "program_manager_deep", q)

    def test_fast_routes_to_8b(self):
        cases = [
            "Summarize today's import health",
            "Focus the claims kanban widget",
            "Show the daily huddle",
            "Parse this short status update for the UI",
        ]
        for q in cases:
            got = classify_intent(q)
            self.assertEqual(got.get("lane"), "chat8b", q)
            self.assertEqual(got.get("reason"), "program_manager_fast", q)

    def test_classify_only_no_llm(self):
        result = orchestrate(
            "Forecast next month collections vs payroll",
            classify_only=True,
            force_enabled=True,
        )
        self.assertTrue(result.get("ok"))
        self.assertTrue(result.get("classifyOnly"))
        self.assertEqual(result.get("lane"), "escalate30b")
        self.assertEqual(result.get("text"), "")
        self.assertFalse(result.get("structured"))

    def test_disabled_blocks_full_execute(self):
        prev = os.environ.pop("NR2_AI_ORCHESTRATOR", None)
        try:
            result = orchestrate("hello", classify_only=False, force_enabled=None)
            self.assertFalse(result.get("ok"))
            self.assertEqual(result.get("error"), "orchestrator_disabled")
        finally:
            if prev is not None:
                os.environ["NR2_AI_ORCHESTRATOR"] = prev

    def test_status_payload_on_hal_status(self):
        from apex_backend import _build_hal_status_payload

        payload = _build_hal_status_payload()
        self.assertIn("orchestrator", payload)
        self.assertIn("enabled", payload["orchestrator"])


if __name__ == "__main__":
    unittest.main()
