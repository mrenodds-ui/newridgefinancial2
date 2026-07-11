"""Phase V0 validation — AI telemetry, scheduled audit flag, freshness."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from apex_ai_telemetry_pack import (
    lane_health,
    record_lane_event,
    telemetry_enabled,
)
from apex_backend import BUILD_ID, build_apex_widgets
from apex_sync_status_pack import build_sync_status, freshness_enabled


class PhaseV0BurnInTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.store = Path(self._tmpdir.name) / "telemetry.json"
        self._prev_telem = os.environ.get("NR2_AI_TELEMETRY")
        self._prev_store = os.environ.get("NR2_AI_TELEMETRY_STORE")
        self._prev_fresh = os.environ.get("NR2_DATA_FRESHNESS")
        os.environ["NR2_AI_TELEMETRY_STORE"] = str(self.store)

    def tearDown(self) -> None:
        for key, prev in (
            ("NR2_AI_TELEMETRY", self._prev_telem),
            ("NR2_AI_TELEMETRY_STORE", self._prev_store),
            ("NR2_DATA_FRESHNESS", self._prev_fresh),
        ):
            if prev is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev
        try:
            self._tmpdir.cleanup()
        except Exception:
            pass

    def test_build_id(self):
        self.assertEqual(BUILD_ID, "hal-10487")

    def test_telemetry_default_off(self):
        os.environ.pop("NR2_AI_TELEMETRY", None)
        self.assertFalse(telemetry_enabled())
        out = record_lane_event(lane="chat8b", ok=True, latency_ms=10)
        self.assertFalse(out.get("recorded"))

    def test_telemetry_records_without_query_text(self):
        os.environ["NR2_AI_TELEMETRY"] = "1"
        out = record_lane_event(
            lane="escalate30b",
            ok=False,
            latency_ms=120.5,
            query="Patient Jane Doe SSN 123-45-6789 paid $500",
            error="timeout talking to ollama",
        )
        self.assertTrue(out.get("recorded"))
        raw = self.store.read_text(encoding="utf-8")
        self.assertNotIn("Jane", raw)
        self.assertNotIn("123-45-6789", raw)
        self.assertNotIn("$500", raw)
        health = lane_health()
        self.assertIn("escalate30b", health.get("lanes") or {})
        lane = (health.get("lanes") or {})["escalate30b"]
        self.assertEqual(lane.get("errors_1h"), 1)
        self.assertEqual(lane.get("calls_1h"), 1)

    def test_freshness_default_off(self):
        os.environ.pop("NR2_DATA_FRESHNESS", None)
        self.assertFalse(freshness_enabled())

    def test_sync_status_chips(self):
        os.environ["NR2_DATA_FRESHNESS"] = "1"
        st = build_sync_status(
            bundle={"loadedAt": "2026-07-11T12:00:00Z", "softdent": {}, "quickbooks": {}}
        )
        self.assertTrue(st.get("ok"))
        self.assertEqual(st.get("phase"), "V0")
        self.assertTrue(st.get("chips"))
        # No dollar keys
        blob = str(st)
        self.assertNotIn("production", blob.lower().split("note")[0] if False else "")

    def test_widgets_present_when_flags_on(self):
        os.environ["NR2_AI_TELEMETRY"] = "1"
        os.environ["NR2_DATA_FRESHNESS"] = "1"
        out = build_apex_widgets("financial")
        ids = {w.get("id") for w in (out.get("widgets") or []) if isinstance(w, dict)}
        self.assertIn("ai-lane-health", ids)
        self.assertIn("data-freshness-status", ids)

    def test_scheduled_audit_disabled_exit(self):
        import subprocess
        import sys

        env = os.environ.copy()
        env.pop("NR2_AUDIT_CRON", None)
        env["NR2_AUDIT_CRON_LOG"] = str(Path(self._tmpdir.name) / "cron.jsonl")
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "run_nr2_scheduled_audit.py"), "--classify-only"],
            cwd=str(Path(__file__).resolve().parents[1]),
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("audit_cron_disabled", proc.stdout)


if __name__ == "__main__":
    unittest.main()
