"""Moonshot WHY-ERRORS Phase 1+2 — SQLite timeout + lock metric tests."""

from __future__ import annotations

import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import practice_source_access as psa
from softdent_practice_exports import read_practice_export_datasets


class WhyErrorsSqliteTimeoutTests(unittest.TestCase):
    def test_read_practice_export_connects_with_timeout_and_busy_timeout(self) -> None:
        mock_conn = MagicMock()
        with (
            patch("softdent_practice_exports.resolve_analytics_db") as resolve_db,
            patch("softdent_practice_exports.relevant_period_labels", return_value=["2026-07"]),
            patch("softdent_practice_exports.sqlite3.connect", return_value=mock_conn) as connect,
            patch("softdent_practice_exports._aggregate_new_patients", return_value=[]),
            patch("softdent_practice_exports._aggregate_treatment_plans", return_value=[]),
            patch("softdent_practice_exports._aggregate_hygiene_recall", return_value=[]),
            patch("softdent_practice_exports._aggregate_operatory_from_db", return_value=[]),
            tempfile.TemporaryDirectory() as tmp,
        ):
            db_path = Path(tmp) / "analytics.sqlite3"
            db_path.write_bytes(b"")
            resolve_db.return_value = db_path
            read_practice_export_datasets()
            connect.assert_called_once()
            args, kwargs = connect.call_args
            self.assertEqual(args[0], db_path)
            self.assertEqual(kwargs.get("timeout"), 10.0)
            mock_conn.execute.assert_any_call("PRAGMA busy_timeout = 5000")
            mock_conn.close.assert_called_once()

    def test_read_practice_export_waits_out_brief_writer_lock(self) -> None:
        """Validation gate: hold a write lock briefly; reader with timeout=10 should succeed."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "analytics.sqlite3"
            setup = sqlite3.connect(db_path)
            setup.execute(
                "CREATE TABLE new_patient_counts (year_month TEXT, new_patient_count INTEGER)"
            )
            setup.execute("INSERT INTO new_patient_counts VALUES ('2026-07', 3)")
            setup.commit()
            setup.close()

            # check_same_thread=False so a release thread can commit on Windows.
            writer = sqlite3.connect(db_path, timeout=10.0, check_same_thread=False)
            writer.execute("BEGIN IMMEDIATE")
            writer.execute("INSERT INTO new_patient_counts VALUES ('2026-06', 1)")
            released = threading.Event()

            def _release() -> None:
                time.sleep(0.4)
                writer.commit()
                writer.close()
                released.set()

            threading.Thread(target=_release, daemon=True).start()

            try:
                with (
                    patch(
                        "softdent_practice_exports.resolve_analytics_db",
                        return_value=db_path,
                    ),
                    patch(
                        "softdent_practice_exports.relevant_period_labels",
                        return_value=["2026-07", "2026-06"],
                    ),
                ):
                    out = read_practice_export_datasets()
                self.assertIsNotNone(out.get("newPatients"))
                rows = out["newPatients"].get("rows") or []
                self.assertTrue(any(int(r.get("Count") or 0) == 3 for r in rows))
            finally:
                released.wait(timeout=5.0)
                if not released.is_set():
                    try:
                        writer.rollback()
                        writer.close()
                    except Exception:
                        pass

    def test_assemble_direct_import_lock_metric_on_operational_error(self) -> None:
        before = psa.direct_import_lock_rejection_count
        with (
            patch(
                "import_direct_pipeline.pipeline_first_imports_enabled",
                return_value=True,
            ),
            patch(
                "import_direct_pipeline.build_softdent_pipeline_datasets",
                side_effect=sqlite3.OperationalError("database is locked"),
            ),
            patch.object(psa, "_fetch_softdent", return_value={}),
            patch.object(psa, "_fetch_quickbooks", return_value={}),
            patch.object(psa, "_payload_to_dataset", return_value=None),
            patch.object(psa, "_dashboard_from_bridge_fallback", return_value=None),
            self.assertLogs(psa.logger, level="WARNING") as captured,
        ):
            result = psa.assemble_direct_import_sections()

        self.assertEqual(psa.direct_import_lock_rejection_count, before + 1)
        self.assertIn("database is locked", str(result.get("directPipelineError") or ""))
        joined = "\n".join(captured.output)
        self.assertIn("direct_import_lock_rejection_count", joined)
        self.assertNotIn("Direct import pipeline unavailable; falling back to legacy fetch", joined)


if __name__ == "__main__":
    unittest.main()
