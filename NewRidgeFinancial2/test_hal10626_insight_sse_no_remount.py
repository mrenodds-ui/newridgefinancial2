"""hal-10628 — insight SSE client must not hard-remount HAL chat."""

from __future__ import annotations

import unittest
from pathlib import Path

from apex_backend import BUILD_ID


ROOT = Path(__file__).resolve().parent
SSE_JS = ROOT / "site" / "nr2-insight-sse.js"


class Hal10626InsightSseNoRemountTests(unittest.TestCase):
    def test_build_id(self):
        self.assertEqual(BUILD_ID, "hal-10631")

    def test_sse_client_never_hard_remounts_hal(self):
        text = SSE_JS.read_text(encoding="utf-8")
        self.assertIn("Never hard-remounts #hal", text)
        # Guard against regression: remounting HAL from SSE wiped the composer.
        self.assertNotIn("Apex.loadPage", text)
        self.assertNotIn('.loadPage("hal"', text)
        self.assertNotIn(".loadPage('hal'", text)


if __name__ == "__main__":
    unittest.main()
