"""Tests for backup_db (hal-10073)."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backup_db import backup_db
from operator_audit_store import append_operator_audit, init_operator_audit_schema, read_operator_audit_tail
from sidenotes_local_store import init_sidenotes_local_schema, insert_sidenote_local, list_sidenotes_local


class BackupDbTests(unittest.TestCase):
    def test_backup_writes_sqlite_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "nr2.sqlite3"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE probe (x INTEGER)")
            conn.commit()
            conn.close()
            result = backup_db(db, retain=3, include_cache=False)
            self.assertTrue(result.get("ok"), result)
            dest = Path(str(result.get("path") or ""))
            self.assertTrue(dest.is_file())
            self.assertGreater(dest.stat().st_size, 0)


class OperatorAuditTests(unittest.TestCase):
    def test_append_and_read_operator_audit(self) -> None:
        conn = sqlite3.connect(":memory:")
        init_operator_audit_schema(conn)
        append_operator_audit(conn, action="navigate:financial", page_key="financial", widget_key="nr2KpiRibbon")
        items = read_operator_audit_tail(conn, limit=5)
        conn.close()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["action"], "navigate:financial")


class SidenotesLocalTests(unittest.TestCase):
    def test_insert_and_list_sidenote(self) -> None:
        conn = sqlite3.connect(":memory:")
        init_sidenotes_local_schema(conn)
        note = insert_sidenote_local(conn, text="Front desk needs assist", source="workstation", station="Room 1")
        notes = list_sidenotes_local(conn, limit=10)
        conn.close()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["id"], note["id"])
        self.assertIn("assist", notes[0]["text"])


if __name__ == "__main__":
    unittest.main()
