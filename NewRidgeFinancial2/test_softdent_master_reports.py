"""SoftDent master report catalog — unit tests (no live SoftDent required)."""

from __future__ import annotations

import unittest
from datetime import date

from softdent_master_reports import (
    format_master_reports_hal_reply,
    gui_export_ids_required,
    load_master_reports,
    verify_master_reports,
)


class SoftDentMasterReportsTests(unittest.TestCase):
    def test_master_catalog_shape(self):
        cat = load_master_reports()
        self.assertEqual(cat.get("version"), 3)
        order = cat.get("masterOrder") or []
        self.assertIn("sd_odbc_core", order)
        self.assertIn("register", order)
        self.assertTrue(cat["reports"]["register"].get("excelExport"))
        self.assertTrue(cat["reports"]["collections"].get("excelExport"))
        self.assertTrue(cat["reports"]["collections"].get("printPreviewAvailable"))
        self.assertTrue(cat["reports"]["collections"].get("visualReadLastPageForTotals"))
        for rid in order:
            self.assertIn(rid, cat["reports"])
            meta = cat["reports"][rid]
            self.assertIn(meta.get("preferredSource"), ("database", "gui"))

    def test_gui_export_ids_include_excel_reports(self):
        from softdent_gui_export import load_menu_map
        from softdent_master_reports import print_preview_report_ids

        self.assertIn("collections", gui_export_ids_required())
        self.assertIn("collections", print_preview_report_ids())
        menu = load_menu_map()
        for gid in gui_export_ids_required():
            self.assertIn(gid, menu["reports"], msg=f"missing menu map entry for {gid}")

    def test_verify_runs_without_ui(self):
        result = verify_master_reports(
            start=date(2026, 7, 1),
            end=date(2026, 7, 12),
            require_inbox_files=False,
        )
        self.assertIn("reports", result)
        self.assertIn("database", result)
        self.assertIn("register", result["reports"])
        text = format_master_reports_hal_reply()
        self.assertIn("source of truth", text.lower())
        self.assertIn("Print Preview", text)
        self.assertIn("LAST page", text)
        self.assertIn("Excel", text)

    def test_verify_never_leaks_password(self):
        blob = str(
            verify_master_reports(
                start=date(2026, 7, 1),
                end=date(2026, 7, 12),
            )
        ).lower()
        self.assertNotIn("softdent_signon_password", blob)
        # Allow passwordConfigured-style words only if present elsewhere — strip common false positives
        self.assertNotIn("password=", blob)


if __name__ == "__main__":
    unittest.main()
