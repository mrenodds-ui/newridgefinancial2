"""hal-10628 — Ask HAL paths must not hard-remount a live HAL composer."""

from __future__ import annotations

import unittest
from pathlib import Path

from apex_backend import BUILD_ID


ROOT = Path(__file__).resolve().parent
BRIDGE = ROOT / "site" / "apex-hal-bridge.js"
CORE = ROOT / "site" / "apex-core.js"


class Hal10627AskNoRemountTests(unittest.TestCase):
    def test_build_id(self):
        self.assertEqual(BUILD_ID, "hal-10630")

    def test_bridge_ask_fallback_silent_when_on_hal(self):
        text = BRIDGE.read_text(encoding="utf-8")
        self.assertIn('loadPage("hal", onHal ? { silent: true } : undefined)', text)
        self.assertNotIn('window.Apex.loadPage("hal");', text)

    def test_ask_hal_reuses_live_composer(self):
        text = CORE.read_text(encoding="utf-8")
        self.assertIn("Prefer the live composer", text)
        self.assertIn("Silent polls must not flash the stage", text)


if __name__ == "__main__":
    unittest.main()
