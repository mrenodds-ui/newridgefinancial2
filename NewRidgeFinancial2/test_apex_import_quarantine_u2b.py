"""Phase U2b validation — import quarantine & admin alerts."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID, build_apex_widgets
from apex_import_quarantine_pack import (
    GAP_IMPORT_QUARANTINED,
    clear_failure,
    fail_threshold,
    list_quarantine,
    maybe_quarantine_after_failure,
    quarantine_enabled,
    quarantine_status,
    release_quarantine,
)


class ImportQuarantinePhaseU2bTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmpdir.name)
        self.qdir = self.root / "quarantine"
        self.inbox = self.root / "inbox"
        self.qdir.mkdir()
        self.inbox.mkdir()
        self._prev_q = os.environ.get("NR2_QUARANTINE_DIR")
        self._prev_th = os.environ.get("NR2_IMPORT_FAIL_THRESHOLD")
        os.environ["NR2_QUARANTINE_DIR"] = str(self.qdir)
        os.environ["NR2_IMPORT_FAIL_THRESHOLD"] = "3"

    def tearDown(self) -> None:
        if self._prev_q is None:
            os.environ.pop("NR2_QUARANTINE_DIR", None)
        else:
            os.environ["NR2_QUARANTINE_DIR"] = self._prev_q
        if self._prev_th is None:
            os.environ.pop("NR2_IMPORT_FAIL_THRESHOLD", None)
        else:
            os.environ["NR2_IMPORT_FAIL_THRESHOLD"] = self._prev_th
        try:
            self._tmpdir.cleanup()
        except Exception:
            pass

    def test_build_id(self):
        self.assertEqual(BUILD_ID, "hal-10491")

    def test_flag_default_on(self):
        prev = os.environ.pop("NR2_IMPORT_QUARANTINE", None)
        try:
            self.assertTrue(quarantine_enabled())
            self.assertEqual(fail_threshold(), 3)
        finally:
            if prev is not None:
                os.environ["NR2_IMPORT_QUARANTINE"] = prev

    def test_below_threshold_keeps_file(self):
        f = self.inbox / "poison.csv"
        f.write_text("bad", encoding="utf-8")
        out = maybe_quarantine_after_failure(f, error="parse_fail", attempts=1)
        self.assertTrue(out.get("ok"))
        self.assertFalse(out.get("quarantined"))
        self.assertTrue(f.is_file())
        self.assertEqual(int(out.get("failureCount") or 0), 1)

    def test_threshold_quarantines_and_alerts(self):
        f = self.inbox / "poison.csv"
        f.write_text("bad", encoding="utf-8")
        maybe_quarantine_after_failure(f, error="fail1")
        maybe_quarantine_after_failure(f, error="fail2")
        out = maybe_quarantine_after_failure(f, error="fail3")
        self.assertTrue(out.get("quarantined"))
        self.assertEqual(out.get("gapCode"), GAP_IMPORT_QUARANTINED)
        self.assertFalse(f.is_file())
        rows = list_quarantine(limit=10)
        self.assertTrue(rows)
        self.assertTrue((out.get("adminAlert") or {}).get("ok"))
        insight = (out.get("adminAlert") or {}).get("insight") or {}
        self.assertIsNone((insight.get("data") or {}).get("value"))

    def test_release(self):
        f = self.inbox / "retry_me.csv"
        f.write_text("x", encoding="utf-8")
        for _ in range(3):
            maybe_quarantine_after_failure(f, error="x")
        rows = list_quarantine(limit=5)
        self.assertTrue(rows)
        name = rows[0]["name"]
        released = release_quarantine(name, restore_dir=self.inbox)
        self.assertTrue(released.get("ok"))
        restored = Path(str(released.get("releasedTo") or ""))
        self.assertTrue(restored.is_file(), msg=str(released))

    def test_status_and_widget(self):
        st = quarantine_status()
        self.assertEqual(st.get("phase"), "U2b")
        out = build_apex_widgets("financial")
        ids = {w.get("id") for w in (out.get("widgets") or []) if isinstance(w, dict)}
        self.assertIn("import-quarantine-status", ids)

    def test_disabled(self):
        prev = os.environ.get("NR2_IMPORT_QUARANTINE")
        os.environ["NR2_IMPORT_QUARANTINE"] = "0"
        try:
            f = self.inbox / "x.csv"
            f.write_text("x", encoding="utf-8")
            out = maybe_quarantine_after_failure(f, error="e")
            self.assertEqual(out.get("reason"), "quarantine_disabled")
            self.assertTrue(f.is_file())
        finally:
            if prev is None:
                os.environ.pop("NR2_IMPORT_QUARANTINE", None)
            else:
                os.environ["NR2_IMPORT_QUARANTINE"] = prev
            clear_failure("x.csv")


if __name__ == "__main__":
    unittest.main()
