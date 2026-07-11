"""Phase W2 — quarantine review UI (retry/purge panel)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from apex_backend import BUILD_ID, build_apex_widgets
from apex_import_quarantine_pack import (
    maybe_quarantine_after_failure,
    purge_quarantine,
    quarantine_ui_enabled,
    quarantine_widget,
    retry_quarantine,
)


class QuarantinePanelW2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmpdir.name)
        self.qdir = self.root / "quarantine"
        self.inbox = self.root / "inbox"
        self.qdir.mkdir()
        self.inbox.mkdir()
        self._prev_q = os.environ.get("NR2_QUARANTINE_DIR")
        self._prev_th = os.environ.get("NR2_IMPORT_FAIL_THRESHOLD")
        self._prev_ui = os.environ.get("NR2_QUARANTINE_UI")
        os.environ["NR2_QUARANTINE_DIR"] = str(self.qdir)
        os.environ["NR2_IMPORT_FAIL_THRESHOLD"] = "3"
        os.environ["NR2_QUARANTINE_UI"] = "1"

    def tearDown(self) -> None:
        for key, prev in (
            ("NR2_QUARANTINE_DIR", self._prev_q),
            ("NR2_IMPORT_FAIL_THRESHOLD", self._prev_th),
            ("NR2_QUARANTINE_UI", self._prev_ui),
        ):
            if prev is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev
        try:
            self._tmpdir.cleanup()
        except Exception:
            pass

    def test_build_id(self):
        self.assertEqual(BUILD_ID, "hal-10492")

    def test_ui_default_on(self):
        os.environ.pop("NR2_QUARANTINE_UI", None)
        self.assertTrue(quarantine_ui_enabled())

    def _quarantine_one(self) -> str:
        f = self.inbox / "poison.csv"
        f.write_text("bad", encoding="utf-8")
        maybe_quarantine_after_failure(f, error="fail1")
        maybe_quarantine_after_failure(f, error="fail2")
        out = maybe_quarantine_after_failure(f, error="fail3")
        self.assertTrue(out.get("quarantined"))
        name = Path(out.get("path") or "").name
        self.assertTrue(name)
        return name

    def test_widget_panel_shape(self):
        name = self._quarantine_one()
        w = quarantine_widget({})
        self.assertEqual(w.get("type"), "quarantine-panel")
        self.assertEqual(w.get("id"), "import-quarantine-panel")
        items = w.get("items") or []
        self.assertTrue(any(i.get("name") == name for i in items if isinstance(i, dict)))
        self.assertIn("retry", str(w.get("endpoints") or {}))

    def test_purge(self):
        name = self._quarantine_one()
        out = purge_quarantine(name)
        self.assertTrue(out.get("ok"))
        self.assertFalse((self.qdir / name).is_file())
        self.assertFalse((self.qdir / f"{name}.reason.json").is_file())

    def test_retry_calls_queue_import(self):
        name = self._quarantine_one()
        with patch(
            "apex_import_watcher_pack.queue_import",
            return_value={"ok": True, "path": "restored"},
        ) as qi:
            out = retry_quarantine(name, restore_dir=self.inbox)
        self.assertTrue(out.get("ok"))
        self.assertTrue(qi.called)
        self.assertFalse((self.qdir / name).is_file())

    def test_financial_widgets_include_panel(self):
        out = build_apex_widgets("financial")
        ids = {w.get("id") for w in (out.get("widgets") or []) if isinstance(w, dict)}
        self.assertIn("import-quarantine-panel", ids)

    def test_panel_js_present(self):
        site = Path(__file__).resolve().parent / "site"
        js = (site / "apex-quarantine-panel.js").read_text(encoding="utf-8")
        self.assertIn("import-quarantine-retry", js)
        self.assertIn("import-quarantine-purge", js)
        html = (site / "index.html").read_text(encoding="utf-8")
        self.assertIn("apex-quarantine-panel.js", html)


if __name__ == "__main__":
    unittest.main()
