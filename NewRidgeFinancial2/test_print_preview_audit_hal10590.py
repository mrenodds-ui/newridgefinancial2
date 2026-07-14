"""HAL-10590 Print Preview visual-audit protocol (not gold ingest)."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from apex_backend import BUILD_ID
from softdent_odbc_extract import ensure_sd_schema
from softdent_print_preview_audit import (
    PACKAGE_BUILD_ID,
    append_print_preview_audit,
    format_print_preview_audit_reply,
    list_print_preview_audits,
    print_preview_audit_playbook,
    print_preview_audit_widget,
    run_ops_10590_print_preview_audit,
    validate_print_preview_audit_record,
)
from softdent_treatment_planning import ensure_treatment_planning_schema


class PrintPreviewAuditHal10590Tests(unittest.TestCase):
    def test_build_id_coupled(self) -> None:
        self.assertEqual(PACKAGE_BUILD_ID, "hal-10590")
        self.assertEqual(BUILD_ID, "hal-10608")

    def test_visual_audit_does_not_trigger_gold_ingest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            db = dest / "analytics.db"
            conn = sqlite3.connect(str(db))
            try:
                ensure_sd_schema(conn)
                ensure_treatment_planning_schema(conn)
                conn.commit()
            finally:
                conn.close()

            # Point exports at temp so JSONL is isolated
            validated = validate_print_preview_audit_record(
                {
                    "reportType": "InsuranceIncome",
                    "dateRange": "2026-06-01..2026-06-30",
                    "lastPageAggregateTotal": 12345.67,
                    "pageCount": 12,
                    "operatorId": "test",
                }
            )
            self.assertTrue(validated.get("ok"))
            self.assertFalse(validated.get("triggersGoldIngest"))
            self.assertFalse(validated["record"]["triggersGoldIngest"])

            result = append_print_preview_audit(
                {
                    "reportType": "InsuranceIncome",
                    "dateRange": "2026-06-01..2026-06-30",
                    "lastPageAggregateTotal": 12345.67,
                    "pageCount": 12,
                    "operatorId": "test",
                },
                dest=dest,
            )
            self.assertTrue(result.get("ok"))
            self.assertFalse(result.get("triggersGoldIngest"))
            self.assertTrue(result.get("paymentLinesUnchanged"))
            self.assertEqual(result.get("visualAuditLastPageTotal"), 12345.67)
            log = dest / "print_preview_audit_log.jsonl"
            self.assertTrue(log.is_file())
            # Gold lines must not be invented by visual audit
            conn2 = sqlite3.connect(str(db))
            try:
                lines = int(
                    conn2.execute("SELECT COUNT(*) FROM sd_insurance_payment_lines").fetchone()[0]
                )
            finally:
                conn2.close()
            self.assertEqual(lines, 0)

            status = list_print_preview_audits(dest=dest)
            self.assertTrue(status.get("visualAuditAvailable"))
            self.assertFalse(status.get("triggersGoldIngest"))

            run = run_ops_10590_print_preview_audit(dest=dest)
            self.assertFalse(run.get("triggersGoldIngest"))

    def test_rejects_missing_total_and_phi(self) -> None:
        bad = validate_print_preview_audit_record(
            {"reportType": "InsuranceIncome", "lastPageAggregateTotal": None}
        )
        self.assertFalse(bad.get("ok"))
        phi = validate_print_preview_audit_record(
            {
                "reportType": "InsuranceIncome",
                "lastPageAggregateTotal": 100,
                "notes": "patient Jane Doe account #123",
            }
        )
        self.assertFalse(phi.get("ok"))

    def test_playbook_widget_reply(self) -> None:
        play = print_preview_audit_playbook()
        self.assertIn("Print Preview", play["output"])
        self.assertIn("PageDown", play["pages"])
        self.assertIn("does NOT create", play["record"])
        w = print_preview_audit_widget()
        self.assertEqual(w.get("packageBuildId"), "hal-10590")
        self.assertFalse(w.get("triggersGoldIngest"))
        self.assertIn("visual audit only", (w.get("confirmation") or "").lower())
        text = format_print_preview_audit_reply({"visualAuditAvailable": False, "count": 0, "gapCode": "GOLD_CSV_MISSING", "paymentLines": 0})
        self.assertIn("HAL-10590", text)
        self.assertIn("empty != $0", text)


if __name__ == "__main__":
    unittest.main()
