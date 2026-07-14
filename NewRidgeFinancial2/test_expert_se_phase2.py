"""Moonshot Expert SE Phase 2 — threaded server + freshness chip gates."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from apex_sync_status_pack import _level, build_sync_status, freshness_enabled
from nr2_http_server import NR2SSLWSGIRefServer


class ExpertSePhase2Tests(unittest.TestCase):
    def test_ssl_server_uses_threading_mixin(self) -> None:
        """REC-002: HTTPS adapter must use ThreadingMixIn so Ollama cannot block other GETs."""
        import inspect

        src = inspect.getsource(NR2SSLWSGIRefServer.run)
        self.assertIn("ThreadingMixIn", src)
        self.assertIn("ThreadedWSGIServer", src)
        self.assertIn("daemon_threads", src)

    def test_level_seven_day_critical(self) -> None:
        self.assertEqual(_level(1), "fresh")
        self.assertEqual(_level(30), "stale")
        self.assertEqual(_level(167), "stale")
        self.assertEqual(_level(168), "critical")
        self.assertEqual(_level(200), "critical")

    def test_freshness_default_on(self) -> None:
        self.assertTrue(freshness_enabled())

    def test_force_show_when_softdent_critical(self) -> None:
        old = datetime.now(timezone.utc) - timedelta(days=10)
        st = build_sync_status(
            bundle={
                "loadedAt": old.isoformat(),
                "softdent": {"loadedAt": old.isoformat()},
                "quickbooks": {"loadedAt": old.isoformat()},
            }
        )
        self.assertTrue(st.get("forceShow") or st.get("enabled"))
        self.assertEqual(st.get("worstLevel"), "critical")
        softdent = (st.get("chips") or [{}])[0]
        self.assertEqual(softdent.get("level"), "critical")
        self.assertIn("7 days", str(softdent.get("alert") or ""))


if __name__ == "__main__":
    unittest.main()
