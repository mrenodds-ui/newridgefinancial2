"""Tests for NR2 loopback browser security helpers."""

from __future__ import annotations

import sys
import time
import types
import unittest
from unittest import mock

if "bottle" not in sys.modules:
    bottle_stub = types.ModuleType("bottle")
    bottle_stub.request = mock.MagicMock()
    sys.modules["bottle"] = bottle_stub

from nr2_browser_security import (
    SessionVault,
    classify_financial_query,
    host_allowed,
    maybe_rotate_session_token,
    mutation_auth_failure_reason,
    normalize_host,
    origin_allowed_for_mutation,
)
import nr2_browser_security as sec


class NR2BrowserSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        sec._session_vault = SessionVault()

    def test_normalize_host_ipv6(self) -> None:
        self.assertEqual(normalize_host("[::1]:8765"), "[::1]:8765")
        self.assertEqual(normalize_host("127.0.0.1:8765"), "127.0.0.1:8765")

    def test_host_allowed_loopback(self) -> None:
        with mock.patch.object(sec.bottle, "request") as req:
            req.headers = {"Host": "127.0.0.1:8765"}
            self.assertTrue(host_allowed())
        with mock.patch.object(sec.bottle, "request") as req:
            req.headers = {"Host": "attacker.evil.com"}
            self.assertFalse(host_allowed())

    def test_host_rejects_subdomain_localhost(self) -> None:
        with mock.patch.object(sec.bottle, "request") as req:
            req.headers = {"Host": "evil.localhost:8765"}
            self.assertFalse(host_allowed())

    def test_origin_allowed_for_mutation(self) -> None:
        with mock.patch.object(sec.bottle, "request") as req:
            req.headers = {"Origin": "http://127.0.0.1:8765", "Host": "127.0.0.1:8765"}
            self.assertTrue(origin_allowed_for_mutation())
        with mock.patch.object(sec.bottle, "request") as req:
            req.headers = {"Origin": "null", "Host": "127.0.0.1:8765"}
            self.assertFalse(origin_allowed_for_mutation())

    def test_mutation_auth_failure_reason(self) -> None:
        token = "abc123"
        with mock.patch.object(sec.bottle, "request") as req:
            req.headers = {
                "Host": "127.0.0.1:8765",
                "Origin": "http://127.0.0.1:8765",
                "X-NR2-Session-Token": token,
                "User-Agent": "test-agent",
            }
            sec.bind_session_user_agent(token)
            self.assertIsNone(mutation_auth_failure_reason(token))
        with mock.patch.object(sec.bottle, "request") as req:
            req.headers = {
                "Host": "127.0.0.1:8765",
                "Origin": "http://127.0.0.1:8765",
                "X-NR2-Session-Token": "wrong",
                "User-Agent": "test-agent",
            }
            self.assertEqual(mutation_auth_failure_reason(token), "token_invalid")

    def test_classify_financial_query(self) -> None:
        self.assertTrue(classify_financial_query("What is our revenue trend?"))
        self.assertTrue(classify_financial_query("Show A/R aging"))
        self.assertTrue(classify_financial_query("Who owes money?"))
        self.assertFalse(classify_financial_query("Print this page"))

    def test_maybe_rotate_session_token(self) -> None:
        sec._session_vault.register("old-token", ua="test-agent")
        sec._TOKEN_ROTATE_SECONDS = 0
        first, rotated = maybe_rotate_session_token("old-token")
        self.assertTrue(rotated)
        self.assertNotEqual(first, "old-token")
        self.assertFalse(sec._session_vault.validate("old-token", "test-agent"))
        sec._TOKEN_ROTATE_SECONDS = 900


class ImportReadinessOperationTests(unittest.TestCase):
    def test_operation_context_in_readiness(self) -> None:
        from import_diagnostics import assess_import_readiness

        readiness = assess_import_readiness(sync_state=None, operation="tax")
        self.assertIn("operationContext", readiness)
        self.assertIn("thresholds", readiness)
        self.assertEqual(readiness["operationContext"]["activeOperation"], "tax")
        self.assertEqual(readiness["thresholds"]["taxOpsHours"], readiness["operationContext"]["tax"]["maxAgeHours"])

    def test_tax_operation_uses_longer_stale_threshold(self) -> None:
        from import_diagnostics import TAX_OPS_HOURS, _operation_stale_hours

        self.assertEqual(_operation_stale_hours("tax", daily_ops_hours=8, tax_ops_hours=168, ar_ops_hours=24), float(TAX_OPS_HOURS))


if __name__ == "__main__":
    unittest.main()
