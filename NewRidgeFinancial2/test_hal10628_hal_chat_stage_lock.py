"""hal-10628 — HAL chat mount locks stage against remount / form reload."""

from __future__ import annotations

import unittest
from pathlib import Path

from apex_backend import BUILD_ID


ROOT = Path(__file__).resolve().parent
CORE = ROOT / "site" / "apex-core.js"


class Hal10628ChatStageLockTests(unittest.TestCase):
    def test_build_id(self):
        self.assertEqual(BUILD_ID, "hal-10628")

    def test_composer_is_form_with_submit_guard(self):
        text = CORE.read_text(encoding="utf-8")
        self.assertIn('<form class="apex-hal-chat__composer" data-hal-form', text)
        self.assertIn("Always preventDefault on form submit", text)
        self.assertIn("halChatMounted", text)
        self.assertIn("never softRenderHalMain", text)
        self.assertIn('document.querySelector("[data-hal-chat]")', text)


if __name__ == "__main__":
    unittest.main()
