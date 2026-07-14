"""Moonshot import-cache KPIs — single-flight bundle load + per-page progress."""

from __future__ import annotations

import sys
import threading
import types
import unittest
from unittest import mock

if "bottle" not in sys.modules:
    bottle_stub = types.ModuleType("bottle")
    bottle_stub.request = mock.MagicMock()
    bottle_stub.response = mock.MagicMock()
    bottle_stub.response.headers = {}
    sys.modules["bottle"] = bottle_stub

import apex_backend as ab


class SingleFlightBundleLoadTests(unittest.TestCase):
    def setUp(self) -> None:
        with ab._REPORTS_BUNDLE_CACHE_LOCK:
            ab._REPORTS_BUNDLE_CACHE["at"] = 0.0
            ab._REPORTS_BUNDLE_CACHE["reports"] = None
            ab._REPORTS_BUNDLE_CACHE["bundle"] = None
            ab._REPORTS_BUNDLE_CACHE["errors"] = None
        ab._BUNDLE_LOAD_EVENT = None

    def test_concurrent_calls_coalesce_to_one_loader(self) -> None:
        calls = {"n": 0}
        hold = threading.Event()
        release = threading.Event()
        results: list[tuple] = []

        def fake_load_import_bundle(**_kwargs):
            calls["n"] += 1
            hold.set()  # signal loader started
            release.wait(timeout=5)  # stay in-flight so waiters coalesce
            return {"ok": True, "softdent": {}, "diagnostics": {"summary": {}}}

        def fake_build_financial_reports(**_kwargs):
            return {"ok": True}

        def worker() -> None:
            out = ab._load_reports_and_bundle()
            results.append(out)

        with mock.patch("import_loader.load_import_bundle", side_effect=fake_load_import_bundle):
            with mock.patch(
                "financial_reports.build_financial_reports", side_effect=fake_build_financial_reports
            ):
                threads = [threading.Thread(target=worker) for _ in range(4)]
                for t in threads:
                    t.start()
                self.assertTrue(hold.wait(timeout=5), "loader never started")
                # Give waiters time to attach to in-flight event
                __import__("time").sleep(0.2)
                release.set()
                for t in threads:
                    t.join(timeout=15)

        self.assertEqual(len(results), 4)
        self.assertEqual(calls["n"], 1, "single-flight must load import bundle once")
        for reports, bundle, errors in results:
            self.assertIsInstance(reports, dict)
            self.assertIsInstance(bundle, dict)
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
