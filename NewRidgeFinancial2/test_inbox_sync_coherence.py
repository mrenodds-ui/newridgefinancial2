"""Moonshot inbox sync coherence — critical files survive purge; no-op writes are bit-identical."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


class InboxCoherenceTests(unittest.TestCase):
    def test_purge_preserves_critical_filenames(self) -> None:
        from import_cache_ttl import CRITICAL_INBOX_FILENAMES, purge_import_cache

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            softdent = root / "softdent"
            qb = root / "quickbooks"
            softdent.mkdir()
            qb.mkdir()
            (softdent / "softdent_ar_aging.csv").write_text("Bucket,Balance\n0-30,1\n", encoding="utf-8")
            (softdent / "softdent_dashboard_data.json").write_text("[]", encoding="utf-8")
            (qb / "quickbooks_expenses.csv").write_text("Period,TotalExpense\n2026-07,1\n", encoding="utf-8")
            (softdent / "scratch.tmp").write_text("x", encoding="utf-8")
            with mock.patch("import_cache_ttl.softdent_import_dir", return_value=softdent), mock.patch(
                "import_cache_ttl.quickbooks_import_dir", return_value=qb
            ), mock.patch("import_cache_ttl.manifest_path", return_value=root / "import_cache_manifest.json"):
                removed = purge_import_cache(preserve_criticals=True)
            self.assertIn("scratch.tmp", removed)
            self.assertTrue((softdent / "softdent_ar_aging.csv").is_file())
            self.assertTrue((softdent / "softdent_dashboard_data.json").is_file())
            self.assertTrue((qb / "quickbooks_expenses.csv").is_file())
            for name in ("softdent_ar_aging.csv", "softdent_dashboard_data.json", "quickbooks_expenses.csv"):
                self.assertIn(name, CRITICAL_INBOX_FILENAMES)

    def test_purge_if_expired_soft_skips_when_criticals_present(self) -> None:
        from import_cache_ttl import purge_if_expired

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            softdent = root / "softdent"
            qb = root / "quickbooks"
            softdent.mkdir()
            qb.mkdir()
            (softdent / "softdent_ar_aging.csv").write_text("Bucket,Balance\n0-30,100\n", encoding="utf-8")
            (softdent / "softdent_dashboard_data.json").write_text(
                json.dumps([{"period": "2026-07", "production": 1}]), encoding="utf-8"
            )
            expired = {
                "expiresAt": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                "syncedAt": (datetime.now(timezone.utc) - timedelta(days=8)).isoformat(),
            }
            with mock.patch("import_cache_ttl.softdent_import_dir", return_value=softdent), mock.patch(
                "import_cache_ttl.quickbooks_import_dir", return_value=qb
            ), mock.patch("import_cache_ttl.load_manifest", return_value=expired):
                result = purge_if_expired()
            self.assertFalse(result.get("purged"))
            self.assertEqual(result.get("reason"), "retention-soft-skip-criticals-present")
            self.assertTrue((softdent / "softdent_ar_aging.csv").is_file())

    def test_write_text_if_changed_noop(self) -> None:
        from import_cache_ttl import write_text_if_changed

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.json"
            self.assertTrue(write_text_if_changed(path, '{"a":1}'))
            mtime1 = path.stat().st_mtime
            content1 = path.read_bytes()
            self.assertFalse(write_text_if_changed(path, '{"a":1}'))
            self.assertEqual(path.read_bytes(), content1)
            self.assertEqual(path.stat().st_mtime, mtime1)

    def test_sdk_summary_skips_period_expenses(self) -> None:
        from import_sync import _sync_quickbooks_sdk_summary

        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            (dest / "quickbooks_expenses.csv").write_text(
                "Period,TotalExpense\n2026-06,10\n2026-07,20\n", encoding="utf-8"
            )
            before = (dest / "quickbooks_expenses.csv").read_bytes()
            probe = {
                "status": "QUICKBOOKS_SDK_REPORT_DATA_AVAILABLE",
                "total_income": 100,
                "total_expenses": 50,
            }
            (dest / "quickbooks_sdk_report_probe_summary.json").write_text(
                json.dumps(probe), encoding="utf-8"
            )
            with mock.patch("import_sync._auto_pull_exports_enabled", return_value=False), mock.patch(
                "import_sync._recover_expense_categories_csv", return_value=[]
            ):
                _sync_quickbooks_sdk_summary(dest)
            self.assertEqual((dest / "quickbooks_expenses.csv").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
