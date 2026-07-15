"""SoftDent Sign On credential resolver (no secret values in assertions)."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from softdent_signon import (
    ENV_PASSWORD,
    ENV_USER,
    resolve_softdent_signon_credentials,
    softdent_signon_status,
)


class SoftDentSignOnTests(unittest.TestCase):
    def test_status_reports_configured_without_leaking_password(self):
        with mock.patch.dict(
            os.environ,
            {ENV_USER: "Dr", ENV_PASSWORD: "test-secret-not-real"},
            clear=False,
        ):
            status = softdent_signon_status()
            creds = resolve_softdent_signon_credentials()
        self.assertTrue(status.get("ok"))
        self.assertEqual(status.get("user"), "Dr")
        self.assertTrue(status.get("passwordConfigured"))
        self.assertNotIn("password", status)
        self.assertNotIn("test-secret-not-real", str(status))
        self.assertTrue(creds.get("ok"))

    def test_missing_password_is_not_ok(self):
        with mock.patch.dict(os.environ, {ENV_USER: "Dr", ENV_PASSWORD: ""}, clear=False):
            os.environ.pop(ENV_PASSWORD, None)
            os.environ.pop("SOFTDENT_GUI_PASSWORD", None)
            with mock.patch("softdent_signon.load_softdent_signon_env_files", return_value=[]):
                status = softdent_signon_status()
        self.assertFalse(status.get("ok"))
        self.assertFalse(status.get("passwordConfigured"))

    def test_hal_reply_mentions_env_keys_not_password(self):
        with mock.patch.dict(
            os.environ,
            {ENV_USER: "Dr", ENV_PASSWORD: "test-secret-not-real"},
            clear=False,
        ):
            from softdent_signon import format_softdent_signon_hal_reply

            text = format_softdent_signon_hal_reply()
        self.assertIn("SOFTDENT_SIGNON_USER", text)
        self.assertIn("SOFTDENT_SIGNON_PASSWORD", text)
        self.assertIn("environment", text.lower())
        self.assertNotIn("test-secret-not-real", text)

    def test_local_policy_signon(self):
        from nr2_hal_gateway import try_local_policy_reply

        with mock.patch.dict(
            os.environ,
            {ENV_USER: "Dr", ENV_PASSWORD: "test-secret-not-real"},
            clear=False,
        ):
            hit = try_local_policy_reply("Where is the SoftDent Sign On password?")
        self.assertIsNotNone(hit)
        self.assertEqual(hit.get("intent"), "policy:softdent-signon-env")
        self.assertIn("SOFTDENT_SIGNON_PASSWORD", hit.get("text") or "")
        self.assertNotIn("test-secret-not-real", hit.get("text") or "")

    def test_hal_reply_includes_ui_only_data_doctrine(self):
        from softdent_signon import SOFTDENT_DATA_ACCESS_DOCTRINE, format_softdent_signon_hal_reply

        text = format_softdent_signon_hal_reply(
            {
                "user": "Dr",
                "passwordConfigured": True,
            }
        )
        self.assertIn("source of truth", text.lower())
        self.assertIn("Sign On", text)
        self.assertIn("Excel", text)
        self.assertIn(SOFTDENT_DATA_ACCESS_DOCTRINE[:40], text)

    def test_local_policy_ui_only_data_path(self):
        from nr2_hal_gateway import try_local_policy_reply
        from softdent_signon import SOFTDENT_DATA_ACCESS_DOCTRINE

        with mock.patch.dict(
            os.environ,
            {ENV_USER: "Dr", ENV_PASSWORD: "test-secret-not-real"},
            clear=False,
        ):
            hit = try_local_policy_reply(
                "How do I get SoftDent data that cannot be reached by the database?"
            )
        self.assertIsNotNone(hit)
        self.assertEqual(hit.get("intent"), "policy:softdent-signon-env")
        self.assertIn("source of truth", (hit.get("text") or "").lower())
        self.assertIn("Excel", hit.get("text") or "")
        self.assertNotIn("test-secret-not-real", hit.get("text") or "")
        self.assertIn("Sign On", SOFTDENT_DATA_ACCESS_DOCTRINE)

    def test_account_tx_excel_hal_reply(self):
        from softdent_signon import (
            format_softdent_account_tx_excel_hal_reply,
            _query_touches_softdent_account_tx,
            compile_softdent_signon_guidance,
        )

        text = format_softdent_account_tx_excel_hal_reply()
        self.assertIn("Trans for a Period", text)
        self.assertIn("List Each Transaction Separately", text)
        self.assertIn("Excel", text)
        self.assertIn("SDWIN", text)
        self.assertIn(r"C:\SoftDentReportExports", text)
        self.assertIn("NEVER type SoftDentReportExports", text)
        self.assertIn("Select File Name", text)
        self.assertNotIn(r"into C:\SoftDentReportExports (short path C:\SOFTDE~1)", text)
        self.assertIn("Printer", text)
        self.assertTrue(_query_touches_softdent_account_tx("How do I pull SoftDent account transactions to Excel?"))
        self.assertTrue(_query_touches_softdent_account_tx("export transactions for a period"))
        guided = compile_softdent_signon_guidance(
            "How do I pull SoftDent account transactions via Excel?"
        )
        self.assertIn("Trans for a Period", guided)
        self.assertIn("List Each Transaction Separately", guided)

    def test_local_policy_account_tx_excel(self):
        from nr2_hal_gateway import try_local_policy_reply

        with mock.patch.dict(
            os.environ,
            {ENV_USER: "Dr", ENV_PASSWORD: "test-secret-not-real"},
            clear=False,
        ):
            hit = try_local_policy_reply(
                "How do I pull SoftDent account transactions to Excel?"
            )
        self.assertIsNotNone(hit)
        self.assertEqual(hit.get("intent"), "policy:softdent-signon-env")
        text = hit.get("text") or ""
        self.assertIn("Trans for a Period", text)
        self.assertIn("List Each Transaction Separately", text)
        self.assertIn("SoftDentReportExports", text)
        self.assertIn("NEVER type SoftDentReportExports", text)
        self.assertNotIn("test-secret-not-real", text)


if __name__ == "__main__":
    unittest.main()
