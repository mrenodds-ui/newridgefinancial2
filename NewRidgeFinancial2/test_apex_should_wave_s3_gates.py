"""Phase S3 + SHOULD-wave closeout gates (no Ollama)."""

from __future__ import annotations

import os
import unittest

from apex_backend import BUILD_ID
from apex_orchestrator_pack import orchestrator_enabled, orchestrator_status
from apex_orchestrator_polish_pack import should_wave_status


class ShouldWavePhaseS3Gates(unittest.TestCase):
    def test_build_id(self):
        self.assertEqual(BUILD_ID, "hal-10479")

    def test_flag_still_default_off(self):
        prev = os.environ.pop("NR2_AI_ORCHESTRATOR", None)
        try:
            self.assertFalse(orchestrator_enabled())
            st = orchestrator_status()
            self.assertEqual(st.get("orchestratorDefault"), "OFF")
            self.assertFalse(st.get("enabled"))
        finally:
            if prev is not None:
                os.environ["NR2_AI_ORCHESTRATOR"] = prev

    def test_should_wave_complete(self):
        st = orchestrator_status()
        self.assertEqual(st.get("phase"), "S3")
        self.assertTrue(st.get("mustWaveComplete"))
        self.assertTrue(st.get("shouldWaveComplete"))
        self.assertTrue(st.get("burnInChecklist"))

        sw = should_wave_status()
        self.assertTrue(sw.get("ok"))
        self.assertTrue(sw.get("shouldWaveComplete"))
        self.assertEqual(sw.get("phases"), ["S0", "S1", "S2", "S3"])
        self.assertFalse(sw.get("sseStreaming"))


if __name__ == "__main__":
    unittest.main()
