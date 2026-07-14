"""Moonshot crash/perf bottlenecks — singleton, Sync semaphore, fill progress."""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

if "bottle" not in sys.modules:
    bottle_stub = types.ModuleType("bottle")
    bottle_stub.request = mock.MagicMock()
    bottle_stub.response = mock.MagicMock()
    bottle_stub.response.headers = {}
    sys.modules["bottle"] = bottle_stub

import apex_backend as ab
import browser_app as ba


class SingletonGuardTests(unittest.TestCase):
    def test_pid_alive_self(self) -> None:
        self.assertTrue(ba._pid_alive(os.getpid()))

    def test_ensure_singleton_blocks_live_pid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / ".nr2_browser_app.pid"
            # Fake "other" live PID — not our own (same-PID re-entry is allowed).
            pidfile.write_text("424242", encoding="utf-8")
            with mock.patch.object(ba, "PIDFILE", pidfile):
                with mock.patch.object(ba, "_pid_alive", return_value=True):
                    with self.assertRaises(SystemExit) as ctx:
                        ba.ensure_singleton()
                    self.assertEqual(ctx.exception.code, 1)

    def test_ensure_singleton_replaces_stale_pid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / ".nr2_browser_app.pid"
            pidfile.write_text("99999999", encoding="utf-8")  # unlikely live
            with mock.patch.object(ba, "PIDFILE", pidfile):
                ba.ensure_singleton()
            self.assertEqual(pidfile.read_text(encoding="utf-8").strip(), str(os.getpid()))


class SyncSemaphoreTests(unittest.TestCase):
    def setUp(self) -> None:
        ab._SYNC_SEMAPHORE = threading.Semaphore(1)
        ab._FILL_PROGRESS.clear()

    def test_second_sync_returns_locked(self) -> None:
        acquired = ab._SYNC_SEMAPHORE.acquire(blocking=False)
        self.assertTrue(acquired)
        try:
            out = ab.apex_sync_trigger({"page": "financial"})
            self.assertFalse(out.get("ok"))
            self.assertEqual(out.get("status"), "sync_locked")
            self.assertEqual(out.get("retryAfter"), 30)
        finally:
            ab._SYNC_SEMAPHORE.release()


class FillProgressStubTests(unittest.TestCase):
    def setUp(self) -> None:
        ab._WIDGETS_CACHE.clear()
        ab._FILL_PROGRESS.clear()
        ab._update_fill_progress("taxes", 40)

    def tearDown(self) -> None:
        ab._WIDGETS_CACHE.clear()
        ab._FILL_PROGRESS.clear()

    def test_warming_stub_includes_fill_progress(self) -> None:
        # Mark warming already in-progress so we don't spawn a real fill thread.
        ab._WIDGETS_CACHE["taxes:warming"] = {"at": __import__("time").monotonic()}
        with mock.patch.dict(os.environ, {"NR2_WIDGETS_STUB_FASTPATH": "1"}, clear=False):
            stub = ab.build_apex_widgets("taxes")
        self.assertTrue(stub.get("warming"))
        self.assertEqual(stub.get("fillProgress"), 40)
        self.assertEqual(stub.get("fillPage"), "taxes")
        self.assertGreaterEqual(int(stub.get("retryAfter") or 0), 1)
        widgets = stub.get("widgets") or []
        self.assertEqual(widgets[0].get("id"), "warming-bridge")
        self.assertEqual(widgets[0].get("fillProgress"), 40)

    def test_per_page_progress_independent(self) -> None:
        ab._update_fill_progress("softdent", 70)
        ab._update_fill_progress("ar", 10)
        self.assertEqual(ab._get_fill_progress("softdent").get("pct"), 70)
        self.assertEqual(ab._get_fill_progress("ar").get("pct"), 10)
        self.assertEqual(ab._get_fill_progress("claims").get("pct"), 0)


class ReportsBundleTtlTests(unittest.TestCase):
    def test_ttl_aligned_with_widgets(self) -> None:
        self.assertEqual(ab._WIDGETS_CACHE_TTL_SEC, 15.0)
        self.assertEqual(ab._REPORTS_BUNDLE_CACHE_TTL_SEC, 15.0)



class IndexBuildIdAlignmentTests(unittest.TestCase):
    def test_index_html_assets_hal_10608(self) -> None:
        html = (Path(__file__).resolve().parent / "site" / "index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("hal-10608", html)
        self.assertNotIn("hal-10576", html)
        self.assertIn("hal-10608 · bridge", html)


if __name__ == "__main__":
    unittest.main()
