"""Moonshot coding plan tests — Sprint 1-3."""

from __future__ import annotations

import os
import sys
import types
import unittest
from unittest import mock

if "bottle" not in sys.modules:
    bottle_stub = types.ModuleType("bottle")
    bottle_stub.request = mock.MagicMock()
    bottle_stub.response = mock.MagicMock()
    bottle_stub.response.headers = {}
    sys.modules["bottle"] = bottle_stub

from nr2_browser_security import (
    SessionVault,
    classify_financial_query,
    maybe_rotate_session_token,
    session_vault,
)
from nr2_rate_limit import classify_route, is_allowed, reset_for_tests
import nr2_browser_security as sec


class SessionVaultTests(unittest.TestCase):
    def setUp(self) -> None:
        sec._session_vault = SessionVault()

    def test_rotate_invalidates_old_token(self) -> None:
        vault = session_vault()
        vault.register("old-token", ua="agent")
        with mock.patch.object(sec, "_TOKEN_ROTATE_SECONDS", 0):
            new, rotated = maybe_rotate_session_token("old-token")
        self.assertTrue(rotated)
        self.assertNotEqual(new, "old-token")
        self.assertFalse(vault.validate("old-token", "agent"))
        self.assertTrue(vault.validate(new, "agent"))

    def test_indirect_financial_query(self) -> None:
        self.assertTrue(classify_financial_query("Who owes money on this account?"))


class RateLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_for_tests()

    def test_burst_returns_false(self) -> None:
        fp = "test-fp"
        # Default read limit is 300/min; pin a small limit for this unit test.
        with mock.patch.dict(os.environ, {"NR2_RATE_READ_PER_MIN": "5"}, clear=False):
            reset_for_tests()
            for _ in range(5):
                ok, _ = is_allowed(fp, "read")
                self.assertTrue(ok)
            ok, retry = is_allowed(fp, "read")
            self.assertFalse(ok)
            self.assertGreaterEqual(retry, 1)

    def test_hal_route_class(self) -> None:
        self.assertEqual(classify_route("/api/hal/evaluate-query", "POST"), "hal")


class ImportThresholdDefaultsTests(unittest.TestCase):
    def test_moonshot_defaults(self) -> None:
        from import_diagnostics import DAILY_OPS_HOURS, POSTING_MAX_AGE_HOURS, SYNC_STALL_MINUTES

        self.assertEqual(DAILY_OPS_HOURS, 24)
        self.assertEqual(POSTING_MAX_AGE_HOURS, 24)
        self.assertEqual(SYNC_STALL_MINUTES, 12)


class HalGatewayTests(unittest.TestCase):
    def test_stale_financial_blocked(self) -> None:
        from nr2_hal_gateway import evaluate_query

        readiness = {"level": "stale", "ok": False, "loadedAt": "2020-01-01T00:00:00Z"}
        result = evaluate_query(query="What is our revenue?", readiness=readiness)
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("error"), "HAL_UNAVAILABLE_STALE_DATA")


class RBACTests(unittest.TestCase):
    def test_office_manager_capabilities(self) -> None:
        from nr2_rbac import capabilities_for_role, has_capability

        caps = capabilities_for_role("office_manager")
        self.assertIn("write_posting", caps)
        self.assertTrue(has_capability("write_posting", "office_manager"))
        self.assertFalse(has_capability("write_posting", "front_desk"))


if __name__ == "__main__":
    unittest.main()
