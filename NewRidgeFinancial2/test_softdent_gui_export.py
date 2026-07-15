"""SoftDent GUI export helpers — unit tests (no live SoftDent required)."""

from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from softdent_gui_export import (
    _is_softdent_excel_workbook_name,
    load_menu_map,
    resolve_menu_keys,
    run_catalog_exports,
    run_safe_period_exports,
    softdent_report_preview_visible,
)


class SoftDentGuiExportTests(unittest.TestCase):
    def test_menu_map_phase1_ids(self):
        catalog = load_menu_map()
        self.assertEqual(catalog.get("version"), 1)
        order = catalog.get("phase1_order") or []
        for rid in ("register", "collections", "transactions", "daysheet", "aging"):
            self.assertIn(rid, order)
            self.assertIn(rid, catalog["reports"])
            keys = resolve_menu_keys(catalog["reports"][rid])
            self.assertTrue(keys)

    def test_print_preview_mdi_and_page_rule(self):
        self.assertTrue(
            softdent_report_preview_visible(
                ["CS SoftDent Software v19.1.4 - [INSURANCE INCOME REPORT]"]
            )
        )
        self.assertFalse(softdent_report_preview_visible(["Sorting Report"]))
        self.assertFalse(softdent_report_preview_visible(["CS SoftDent Software v19.1.4"]))
        note = (load_menu_map().get("notes") or [])[4]
        self.assertIn("PageDown", note)
        ipa = load_menu_map()["reports"]["insurance_payment_analysis"]
        self.assertEqual(ipa.get("outputMode"), "print_preview_only")
        self.assertFalse(ipa.get("excelExport"))

    def test_run_safe_period_exports_never_returns_password(self):
        with mock.patch(
            "softdent_gui_export.export_report_by_id",
            return_value=Path(r"C:\SoftDentReportExports\register.xls"),
        ):
            with mock.patch(
                "softdent_signon.softdent_signon_status",
                return_value={"ok": True, "user": "Dr", "passwordConfigured": True},
            ):
                with mock.patch(
                    "softdent_signon.ensure_softdent_signed_on",
                    return_value={
                        "ok": True,
                        "signedOn": True,
                        "steps": ["already_signed_on_main_window"],
                    },
                ):
                    with mock.patch("softdent_gui_export.softdent_main_running", return_value=True):
                        result = run_safe_period_exports(
                            start=date(2026, 7, 1),
                            end=date(2026, 7, 12),
                            do_register=True,
                            do_collections=True,
                            ensure_signon=True,
                        )
        blob = str(result)
        self.assertTrue(result.get("ok"))
        self.assertIn("registerPath", result)
        self.assertNotIn("password", blob.lower().replace("passwordconfigured", ""))
        self.assertTrue((result.get("signOn") or {}).get("passwordConfigured"))

    def test_catalog_dry_run(self):
        result = run_catalog_exports(
            start=date(2026, 7, 1),
            end=date(2026, 7, 12),
            report_ids=["register", "aging"],
            ensure_signon=False,
            dry_run=True,
        )
        self.assertTrue(result.get("ok"))
        self.assertTrue(result["reports"]["register"].get("dryRun"))
        self.assertTrue(result["reports"]["aging"].get("dryRun"))

    def test_prepare_for_next_report_exists(self):
        from softdent_gui_export import cancel_stale_report_dialogs, prepare_softdent_for_next_report

        self.assertTrue(callable(cancel_stale_report_dialogs))
        self.assertTrue(callable(prepare_softdent_for_next_report))

    def test_softdent_excel_workbook_names(self):
        self.assertTrue(_is_softdent_excel_workbook_name("SDWIN12.csv"))
        self.assertTrue(_is_softdent_excel_workbook_name("REG2607.XLS"))
        self.assertTrue(_is_softdent_excel_workbook_name("COL260714.XLS"))
        self.assertTrue(_is_softdent_excel_workbook_name("AGE260713.XLS"))
        self.assertFalse(_is_softdent_excel_workbook_name("Budget.xlsx"))
        self.assertFalse(_is_softdent_excel_workbook_name("Book1"))

    def test_validate_export_rejects_tiny_file(self):
        from softdent_gui_export import EXPORT_MIN_BYTES, _validate_export_file
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            tiny = Path(td) / "tiny.xls"
            tiny.write_bytes(b"x" * max(1, EXPORT_MIN_BYTES - 1))
            with self.assertRaises(RuntimeError):
                _validate_export_file(tiny, report_id="aging")
            ok = Path(td) / "ok.xls"
            ok.write_bytes(b"x" * EXPORT_MIN_BYTES)
            self.assertEqual(_validate_export_file(ok, report_id="aging"), EXPORT_MIN_BYTES)

    def test_export_report_by_id_retries_then_succeeds(self):
        from softdent_gui_export import EXPORT_MIN_BYTES, export_report_by_id
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "out.xls"
            dest.write_bytes(b"x" * EXPORT_MIN_BYTES)
            calls = {"n": 0}

            def once(*_a, **_k):
                calls["n"] += 1
                if calls["n"] < 2:
                    raise RuntimeError("transient dialog")
                return dest

            with mock.patch("softdent_gui_export.softdent_main_running", return_value=True):
                with mock.patch("softdent_gui_export.prepare_softdent_for_next_report", return_value={"ok": True}):
                    with mock.patch("softdent_gui_export._export_report_by_id_once", side_effect=once):
                        with mock.patch("softdent_gui_export.time.sleep", return_value=None):
                            out = export_report_by_id(
                                "aging",
                                start=date(2026, 7, 1),
                                end=date(2026, 7, 15),
                                retries=2,
                            )
            self.assertEqual(out, dest)
            self.assertEqual(calls["n"], 2)


if __name__ == "__main__":
    unittest.main()
