"""Phase S2 validation — proactive health monitor (no Ollama)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from apex_health_monitor_pack import run_scheduled_health_audit


class HealthMonitorPhaseS2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self._tmpdir.name) / "nr2_unified_s2.db"

    def tearDown(self) -> None:
        try:
            self._tmpdir.cleanup()
        except Exception:
            pass

    def test_disabled_orchestrator_noop(self):
        prev = os.environ.pop("NR2_AI_ORCHESTRATOR", None)
        try:
            result = run_scheduled_health_audit(
                classify_only=True,
                force_orchestrator=False,
                db_path=self.db_path,
            )
            self.assertFalse(result.get("ok"))
            self.assertEqual(result.get("reason"), "orchestrator_disabled")
        finally:
            if prev is not None:
                os.environ["NR2_AI_ORCHESTRATOR"] = prev

    def test_classify_only_deep_lane(self):
        result = run_scheduled_health_audit(
            classify_only=True,
            force_orchestrator=True,
            db_path=self.db_path,
        )
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("phase"), "S2")
        self.assertEqual(result.get("lane"), "escalate30b")
        self.assertTrue(result.get("classifyOnly"))


if __name__ == "__main__":
    unittest.main()
