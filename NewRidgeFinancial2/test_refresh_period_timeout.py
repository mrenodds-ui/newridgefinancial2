"""SoftDent refresh-period must fail-fast — never hang after FuturesTimeout."""

from __future__ import annotations

import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout


def _run_with_hard_timeout(fn, *, timeout_s: float = 0.3):
    """Same pattern as apex refresh-period route: shutdown(wait=False) after timeout."""
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        fut = pool.submit(fn)
        return fut.result(timeout=timeout_s)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


class RefreshPeriodTimeoutTests(unittest.TestCase):
    def test_hard_timeout_returns_without_waiting_for_worker(self) -> None:
        def slow() -> str:
            time.sleep(5.0)
            return "done"

        started = time.monotonic()
        with self.assertRaises(FuturesTimeout):
            _run_with_hard_timeout(slow, timeout_s=0.25)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 1.5, msg=f"hung {elapsed:.2f}s — shutdown(wait=True) leak?")

    def test_route_source_uses_wait_false(self) -> None:
        from pathlib import Path

        src = Path(__file__).with_name("apex_backend.py").read_text(encoding="utf-8")
        self.assertIn("pool.shutdown(wait=False, cancel_futures=True)", src)
        self.assertIn("refresh_period_timeout", src)
        # Must not use context-manager that waits on hung SoftDent work
        marker = "def apex_softdent_refresh_period"
        i = src.find(marker)
        self.assertGreater(i, 0)
        window = src[i : i + 1800]
        self.assertNotIn("with ThreadPoolExecutor", window)


if __name__ == "__main__":
    unittest.main()
