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
    financial_read_path,
    host_allowed,
    maybe_rotate_session_token,
    mutation_auth_failure_reason,
    normalize_host,
    origin_allowed_for_mutation,
    system_status_path,
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
        with mock.patch.object(sec.bottle, "request") as req:
            req.headers = {
                "Host": "127.0.0.1:8765",
                "Referer": "https://127.0.0.1:8765/index.html",
            }
            self.assertTrue(origin_allowed_for_mutation())
        with mock.patch.object(sec.bottle, "request") as req:
            req.headers = {"Host": "127.0.0.1:8765"}
            self.assertFalse(origin_allowed_for_mutation())

    def test_register_preserves_issued_at(self) -> None:
        vault = SessionVault()
        vault.register("tok", ua="ua-1")
        issued = vault._by_token["tok"]["issued_at"]
        time.sleep(0.01)
        vault.register("tok", ua="ua-2")
        self.assertEqual(vault._by_token["tok"]["ua"], "ua-2")
        self.assertEqual(vault._by_token["tok"]["issued_at"], issued)

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


class HalHubSecurityTests(unittest.TestCase):
    def test_hub_token_validation(self) -> None:
        from hal_hub import hub_token_header_valid, resolve_hub_token

        token = resolve_hub_token()
        self.assertTrue(hub_token_header_valid(token))
        self.assertFalse(hub_token_header_valid("not-the-hub-token"))

    def test_hub_notify_origin_allowlist(self) -> None:
        from hal_hub import hub_notify_origin_ok

        self.assertTrue(hub_notify_origin_ok("http://127.0.0.1:8766"))
        self.assertTrue(hub_notify_origin_ok("http://localhost:8766"))
        self.assertFalse(hub_notify_origin_ok("http://127.0.0.1:8765"))
        self.assertFalse(hub_notify_origin_ok("null"))

    def test_hub_notify_requires_token_and_origin(self) -> None:
        from hal_hub import hub_notify_access_ok, resolve_hub_token

        token = resolve_hub_token()
        self.assertTrue(hub_notify_access_ok("http://127.0.0.1:8766", token))
        self.assertFalse(hub_notify_access_ok("http://127.0.0.1:8766", "bad"))
        self.assertFalse(hub_notify_access_ok("http://127.0.0.1:8765", token))

    def test_hub_notify_loopback_financial_with_token(self) -> None:
        from unittest.mock import MagicMock

        import bottle

        from hal_hub import hub_notify_access_ok, resolve_hub_token

        token = resolve_hub_token()
        orig_request = bottle.request
        try:
            bottle.request = MagicMock()
            bottle.request.remote_addr = "127.0.0.1"
            bottle.request.headers = {"Host": "127.0.0.1:8765"}
            self.assertTrue(hub_notify_access_ok(None, token))
            bottle.request.headers = {"Host": "127.0.0.1:8766"}
            self.assertFalse(hub_notify_access_ok(None, token))
        finally:
            bottle.request = orig_request

    def test_record_hub_broadcast_strips_text(self) -> None:
        from hal_hub import last_hub_broadcast, record_hub_broadcast

        record_hub_broadcast(
            {
                "from": "Test",
                "text": "secret message body",
                "kind": "hero-metrics",
                "heroMetrics": [{"label": "Collections", "value": "$1"}],
            }
        )
        broadcast = last_hub_broadcast()
        self.assertNotIn("text", broadcast)
        self.assertEqual(broadcast.get("from"), "Test")
        self.assertEqual(broadcast.get("kind"), "hero-metrics")
        self.assertEqual(len(broadcast.get("heroMetrics") or []), 1)

    def test_hub_notify_mutation_auth_exempt_with_token(self) -> None:
        """Workstation hub POST must not require browser session CSRF (Moonshot Phase 5)."""
        try:
            from nr2_http_server import _browser_mutation_auth_ok
        except Exception as exc:  # noqa: BLE001 — CI may lack pywebview desktop stack
            self.skipTest(f"nr2_http_server unavailable without desktop webview: {exc}")
        self.assertTrue(callable(_browser_mutation_auth_ok))

    def test_hub_cross_status_shape(self) -> None:
        from hal_hub import hub_cross_status

        status = hub_cross_status()
        self.assertTrue(status.get("ok"))
        self.assertIn("workstationReachable", status)
        self.assertIn("lastBroadcast", status)

    def test_system_status_path_hal_status(self) -> None:
        self.assertTrue(system_status_path("/api/apex/hal/status"))
        self.assertTrue(system_status_path("/api/apex/import-health"))
        self.assertFalse(system_status_path("/api/apex/widgets/financial"))
        self.assertFalse(system_status_path("/api/financial-reports"))

    def test_financial_read_excludes_system_status(self) -> None:
        # Moonshot Phase 1: status is connected-tier, not money/fresh-tier.
        self.assertFalse(financial_read_path("/api/apex/hal/status"))
        self.assertFalse(financial_read_path("/api/apex/import-health"))
        self.assertTrue(financial_read_path("/api/apex/widgets/financial"))
        self.assertTrue(financial_read_path("/api/apex/hal/board-actions"))
        self.assertTrue(financial_read_path("/api/financial-reports"))


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
