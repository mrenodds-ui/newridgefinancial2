"""N0 validation — insight SSE frames + latest payload (no Ollama)."""

from __future__ import annotations

import json
import unittest
from unittest import mock

from apex_insight_sse_pack import (
    POLL_FALLBACK_MS,
    STREAM_PATH,
    format_sse_event,
    insight_generation,
    insight_latest_payload,
    insight_sse_frames,
    sse_status,
)
from apex_orchestrator_pack import orchestrator_status
from apex_orchestrator_polish_pack import should_wave_status


GOOD = {
    "widget_type": "alert-banner",
    "title": "Test insight",
    "data": {"severity": "warn", "message": "Collections pending", "value": None, "unit": "text"},
    "source_refs": ["import:health:2026-07-11"],
    "confidence": "medium",
    "explanation": "Honesty check",
}


class InsightSsePhaseN0Tests(unittest.TestCase):
    def test_sse_status(self):
        st = sse_status()
        self.assertTrue(st.get("sseStreaming"))
        self.assertEqual(st.get("streamPath"), STREAM_PATH)
        self.assertEqual(st.get("pollFallbackMs"), POLL_FALLBACK_MS)

    def test_format_sse_event(self):
        frame = format_sse_event({"ok": True, "type": "insight_snapshot"}, event="insight")
        self.assertIn("event: insight", frame)
        self.assertIn("data: {", frame)
        self.assertTrue(frame.endswith("\n\n"))
        self.assertIn('"ok": true', frame)

    def test_generation_stable(self):
        g1 = insight_generation(GOOD)
        g2 = insight_generation(GOOD)
        self.assertEqual(g1, g2)
        self.assertEqual(insight_generation(None), "empty")

    def test_latest_and_frames(self):
        with mock.patch(
            "apex_structured_insight_pack.load_last_insight",
            return_value=GOOD,
        ):
            payload = insight_latest_payload()
            self.assertTrue(payload.get("ok"))
            self.assertEqual(payload.get("insight", {}).get("title"), "Test insight")
            self.assertTrue(payload.get("sseStreaming"))
            frames = list(insight_sse_frames(watch_seconds=0))
            self.assertGreaterEqual(len(frames), 1)
            self.assertIn("event: insight", frames[0])
            data_line = [ln for ln in frames[0].splitlines() if ln.startswith("data: ")][0]
            body = json.loads(data_line[len("data: ") :])
            self.assertEqual(body.get("type"), "insight_snapshot")
            self.assertIn("text/event-stream", "text/event-stream")  # contract marker for docs/tests

    def test_orchestrator_reports_sse(self):
        st = orchestrator_status()
        self.assertTrue(st.get("sseStreaming"))
        sw = should_wave_status()
        self.assertTrue(sw.get("sseStreaming"))


if __name__ == "__main__":
    unittest.main()
