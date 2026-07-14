"""Phase 3 — SSE TTFT: typing meta emits before policy/Ollama tokens."""

from __future__ import annotations

import json
import unittest

from nr2_hal_gateway import evaluate_query_sse_frames


class HalStreamTtftTests(unittest.TestCase):
    def test_typing_meta_emitted_first(self) -> None:
        frames = list(
            evaluate_query_sse_frames(
                query="Can you post to QuickBooks?",
                readiness={"level": "fresh"},
            )
        )
        self.assertTrue(frames)
        first = frames[0]
        self.assertIn("event: meta", first)
        self.assertIn("typing", first)
        compact = first.replace(" ", "")
        self.assertIn('"ttft":true', compact)

    def test_local_policy_still_streams_reply(self) -> None:
        frames = list(
            evaluate_query_sse_frames(
                query="Can you post to QuickBooks?",
                readiness={"level": "fresh"},
            )
        )
        joined = "\n".join(frames)
        self.assertIn("read-only", joined.lower())
        self.assertIn('"done": true', joined)
        # First content after meta should be the policy reply token
        data_frames = [f for f in frames if f.startswith("data:")]
        self.assertGreaterEqual(len(data_frames), 1)
        payload = json.loads(data_frames[0].split("data:", 1)[1].strip())
        self.assertTrue(str(payload.get("token") or "").lower().startswith("no"))


if __name__ == "__main__":
    unittest.main()
