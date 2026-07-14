"""HAL-10597 / gold-ops-v19-honest — Print Preview playbook honesty tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID
from softdent_gold_csv_drop_ops import (
    PACKAGE_BUILD_ID,
    checklist_pre_drop,
    format_gold_csv_drop_ops_reply,
    gold_csv_drop_ops_widget,
    gold_csv_drop_playbook,
)
from softdent_odbc_extract import ensure_sd_schema
from softdent_treatment_planning import ensure_treatment_planning_schema
import sqlite3


def _empty_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        ensure_sd_schema(conn)
        ensure_treatment_planning_schema(conn)
        conn.commit()
    finally:
        conn.close()


class GoldOpsV19Hal10597Tests(unittest.TestCase):
    def test_build_id_coupled(self) -> None:
        self.assertEqual(PACKAGE_BUILD_ID, "hal-10597")
        self.assertEqual(BUILD_ID, "hal-10608")

    def test_playbook_v19_print_preview_honest(self) -> None:
        play = gold_csv_drop_playbook()
        self.assertEqual(play.get("outputMode"), "print_preview_only")
        self.assertFalse(play.get("excelAvailable"))
        self.assertIn("Print Preview", play.get("format") or "")
        self.assertIn("Insurance Income", play.get("softDentMenu") or "")
        self.assertIn("no menu item", (play.get("softDentMenuDiscovered") or "").lower())
        bridge = play.get("visualAuditBridge") or {}
        self.assertEqual(bridge.get("def"), "HAL-10590")
        self.assertTrue(bridge.get("doesNotCreateGoldLines"))
        self.assertFalse(bridge.get("triggersGoldIngest"))
        self.assertIn("invent gold", (play.get("never") or "").lower())
        steps = (play.get("whenPrintPreviewOnly") or {}).get("steps") or []
        self.assertTrue(any("HAL-10590" in s for s in steps))
        self.assertTrue(any("GOLD_CSV_MISSING" in s for s in steps))

    def test_pre_checklist_stays_missing_without_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "a.db"
            drop = Path(tmp) / "exports"
            drop.mkdir()
            _empty_db(db)
            pre = checklist_pre_drop(db_path=db, search_dir=drop)
            self.assertEqual((pre.get("audit") or {}).get("gapCode"), "GOLD_CSV_MISSING")
            self.assertFalse(pre.get("readyForIngest"))

    def test_widget_and_reply_honesty(self) -> None:
        w = gold_csv_drop_ops_widget()
        self.assertEqual(w.get("packageBuildId"), "hal-10597")
        self.assertEqual(w.get("def"), "HAL-10597")
        self.assertFalse(w.get("triggersGoldIngest"))
        self.assertFalse(w.get("excelAvailable"))
        self.assertEqual(w.get("outputMode"), "print_preview_only")
        self.assertTrue(w.get("emptyIsNotZero"))
        text = format_gold_csv_drop_ops_reply(
            {"post": {"audit": {"gapCode": "GOLD_CSV_MISSING", "paymentLines": 0}, "passCount": 0, "stepCount": 4}}
        )
        self.assertIn("HAL-10597", text)
        self.assertIn("does NOT create gold lines", text)
        self.assertIn("empty != $0", text)


if __name__ == "__main__":
    unittest.main()
