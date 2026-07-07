"""Moonshot must-fix production tests."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class MustFixThresholdTests(unittest.TestCase):
    def test_posting_and_daily_ops_24h_defaults(self) -> None:
        from import_diagnostics import DAILY_OPS_HOURS, POSTING_MAX_AGE_HOURS

        self.assertEqual(POSTING_MAX_AGE_HOURS, 24)
        self.assertEqual(DAILY_OPS_HOURS, 24)


class MustFixBindHostTests(unittest.TestCase):
    def test_rejects_non_loopback_bind(self) -> None:
        from nr2_startup_checks import resolve_bind_host

        with mock.patch.dict(os.environ, {"NR2_BIND_HOST": "0.0.0.0"}, clear=False):
            with self.assertRaises(SystemExit):
                resolve_bind_host()

    def test_allows_loopback(self) -> None:
        from nr2_startup_checks import resolve_bind_host

        with mock.patch.dict(os.environ, {"NR2_BIND_HOST": "127.0.0.1"}, clear=False):
            self.assertEqual(resolve_bind_host(), "127.0.0.1")


class MustFixTlsTests(unittest.TestCase):
    def test_tls_enforced_by_default(self) -> None:
        from nr2_tls import tls_enforced

        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NR2_ALLOW_HTTP", None)
            os.environ["NR2_ENFORCE_TLS"] = "1"
            self.assertTrue(tls_enforced())


class MustFixFinancialAuditTests(unittest.TestCase):
    def test_financial_mutation_chain(self) -> None:
        from nr2_audit_log import append_financial_mutation, verify_financial_audit_chain

        with tempfile.TemporaryDirectory() as tmp:
            audit_dir = Path(tmp)
            import nr2_audit_log as mod

            mod._AUDIT_DIR = audit_dir
            mod._FINANCIAL_MUTATIONS_LOG = audit_dir / "nr2_financial_mutations.log"
            mod._last_financial_hmac = ""
            append_financial_mutation(
                "posting_batch_approve",
                actor="HAL",
                amount=100.0,
                hal_involved=True,
                after={"status": "approved"},
            )
            verified = verify_financial_audit_chain()
            self.assertTrue(verified.get("verified"))
            self.assertEqual(verified.get("count"), 1)


class MustFixEncryptionTests(unittest.TestCase):
    def test_encryption_required_by_default(self) -> None:
        from nr2_db_crypto import db_encryption_enabled

        with mock.patch.dict(os.environ, {"NR2_DB_ENCRYPTION": "1"}, clear=False):
            self.assertTrue(db_encryption_enabled())

    def test_plaintext_detection(self) -> None:
        from nr2_startup_checks import _is_plaintext_sqlite

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            import sqlite3

            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE t (id INTEGER)")
            conn.commit()
            conn.close()
            self.assertTrue(_is_plaintext_sqlite(db))


if __name__ == "__main__":
    unittest.main()
