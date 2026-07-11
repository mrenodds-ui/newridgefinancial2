"""Direct-first import mode reads upstream exports before document-inbox cache."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from import_loader import clear_import_bundle_cache_for_tests, direct_first_imports_enabled, load_import_bundle


class DirectFirstImportTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_import_bundle_cache_for_tests()
    def test_direct_first_enabled_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NR2_DIRECT_FIRST_IMPORTS", None)
            self.assertTrue(direct_first_imports_enabled())

    def test_direct_first_can_be_disabled(self) -> None:
        with patch.dict(os.environ, {"NR2_DIRECT_FIRST_IMPORTS": "0"}, clear=False):
            self.assertFalse(direct_first_imports_enabled())

    def test_load_bundle_marks_direct_first_mode(self) -> None:
        with patch.dict(os.environ, {"NR2_DIRECT_FIRST_IMPORTS": "1"}, clear=False):
            with patch("import_loader._load_direct_sections") as mock_direct:
                with patch("import_loader._load_dataset", return_value=None):
                    mock_direct.return_value = {
                        "softdent": {
                            "dashboard": {
                                "sourceFile": "softdent_dashboard_data.json",
                                "modifiedAt": "2026-07-01T12:00:00+00:00",
                                "rows": [{"provider": "Dr. Test", "production": 1000, "collections": 900}],
                                "readSource": "direct",
                            }
                        },
                        "quickbooks": {},
                    }
                    bundle = load_import_bundle(sync=False, deep=False)
        self.assertTrue(bundle.get("directFirst"))
        self.assertEqual(bundle.get("importMode"), "direct-first")
        dashboard = (bundle.get("softdent") or {}).get("dashboard") or {}
        self.assertEqual(dashboard.get("readSource"), "direct")
        self.assertEqual(len(dashboard.get("rows") or []), 1)

    def test_cache_fallback_when_direct_missing(self) -> None:
        with patch.dict(os.environ, {"NR2_DIRECT_FIRST_IMPORTS": "1"}, clear=False):
            with patch("import_loader._load_direct_sections") as mock_direct:
                with patch("import_loader._load_dataset") as mock_cache:
                    mock_direct.return_value = {"softdent": {"claims": None}, "quickbooks": {}}
                    mock_cache.return_value = {
                        "sourceFile": "softdent_claims_export.csv",
                        "modifiedAt": "2026-07-01T12:00:00+00:00",
                        "rows": [{"ClaimId": "C-1"}],
                        "readSource": "cache",
                    }
                    bundle = load_import_bundle(sync=False, deep=False)
        claims = (bundle.get("softdent") or {}).get("claims") or {}
        self.assertEqual(claims.get("readSource"), "cache")
        self.assertEqual(len(claims.get("rows") or []), 1)

    def test_direct_first_prefers_direct_over_fresher_cache(self) -> None:
        with patch.dict(os.environ, {"NR2_DIRECT_FIRST_IMPORTS": "1"}, clear=False):
            with patch("import_loader._load_direct_sections") as mock_direct:
                with patch("import_loader._load_dataset") as mock_cache:
                    mock_direct.return_value = {
                        "softdent": {
                            "dashboard": {
                                "sourceFile": "softdent_dashboard_data.json",
                                "modifiedAt": "2026-06-01T12:00:00+00:00",
                                "rows": [{"provider": "Dr. Test", "production": 1000, "collections": 900}],
                                "readSource": "direct",
                            }
                        },
                        "quickbooks": {},
                    }
                    mock_cache.return_value = {
                        "sourceFile": "softdent_dashboard_data.json",
                        "modifiedAt": "2026-07-01T12:00:00+00:00",
                        "rows": [{"provider": "Cache", "production": 500, "collections": 400}],
                        "readSource": "cache",
                    }
                    bundle = load_import_bundle(sync=False, deep=False)
        dashboard = (bundle.get("softdent") or {}).get("dashboard") or {}
        self.assertEqual(dashboard.get("readSource"), "direct")
        self.assertEqual(dashboard.get("rows")[0].get("provider"), "Dr. Test")

    def test_cache_write_serializes_pipeline_claims_rows_not_source_path(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "softdent"
            cache_dir.mkdir()
            daysheet = Path(tmp) / "daysheet.jsonl"
            daysheet.write_text('{"normalized":{"report_date":"2026-05-28"}}\n', encoding="utf-8")
            dataset = {
                "sourceFile": "softdent_claims_export.csv",
                "sourcePath": str(daysheet),
                "modifiedAt": "2026-07-01T12:00:00+00:00",
                "rows": [
                    {
                        "PatientName": "Jane Doe",
                        "ClaimId": "DS-20260528-1",
                        "ClaimStatus": "Pending Review",
                        "ClaimAmount": "137.00",
                    }
                ],
            }
            with patch("import_loader.softdent_import_dir", return_value=cache_dir):
                from import_loader import _write_direct_sections_to_cache

                result = _write_direct_sections_to_cache({"softdent": {"claims": dataset}, "quickbooks": {}})
            dest = cache_dir / "softdent_claims_export.csv"
            self.assertIn(dest.name, result.get("written") or [])
            text = dest.read_text(encoding="utf-8")
            self.assertIn("ClaimId", text)
            self.assertIn("DS-20260528-1", text)
            self.assertNotIn("dataset_name", text)

    def test_cache_write_refreshes_stale_csv_sidecar(self) -> None:
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "softdent"
            cache_dir.mkdir()
            dataset = {
                "sourceFile": "softdent_claims_export.csv",
                "modifiedAt": "2026-07-01T12:00:00+00:00",
                "rows": [
                    {
                        "PatientName": "Jane Doe",
                        "ClaimId": "NEW-1",
                        "ClaimStatus": "Pending Review",
                        "ClaimAmount": "137.00",
                    }
                ],
            }
            stale_csv = cache_dir / "softdent_claims_export.csv"
            stale_csv.write_text("ClaimId\nOLD-1\n", encoding="utf-8")
            stale_sidecar = cache_dir / "softdent_claims_export.json"
            stale_sidecar.write_text(json.dumps([{"ClaimId": "OLD-1"}], indent=2), encoding="utf-8")

            with patch("import_loader.softdent_import_dir", return_value=cache_dir):
                from import_loader import _load_dataset, _write_direct_sections_to_cache

                result = _write_direct_sections_to_cache({"softdent": {"claims": dataset}, "quickbooks": {}})
                loaded = _load_dataset(cache_dir, ("softdent_claims_export.csv",))

            self.assertIn(stale_csv.name, result.get("written") or [])
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual((loaded.get("rows") or [])[0].get("ClaimId"), "NEW-1")

    def test_load_dataset_prefers_rich_claims_over_jane_doe_stub(self) -> None:
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp)
            stub = cache_dir / "softdent_claims_export.csv"
            stub.write_text(
                "ClaimId,PatientName,Payer,ServiceDate,ClaimAmount,ClaimStatus\n"
                "CLM-001,Jane Doe,Delta Dental,2026-06-10,420.0,Ready\n",
                encoding="utf-8",
            )
            rich = cache_dir / "softdent_claims_export.json"
            rich.write_text(
                json.dumps(
                    [
                        {
                            "ClaimId": "DS-20260528-1",
                            "PatientName": "Bernett, Jeffery Adam",
                            "Payer": "Insurance",
                        },
                        {
                            "ClaimId": "DS-20260528-2",
                            "PatientName": "Smith, Ada",
                            "Payer": "Insurance",
                        },
                    ]
                ),
                encoding="utf-8",
            )
            from import_loader import _load_dataset

            loaded = _load_dataset(
                cache_dir,
                ("softdent_claims_export.csv", "softdent_claims_export.json"),
            )
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.get("sourceFile"), "softdent_claims_export.json")
        self.assertEqual(len(loaded.get("rows") or []), 2)
        self.assertNotEqual((loaded.get("rows") or [])[0].get("PatientName"), "Jane Doe")

    def test_write_cache_enabled_by_default(self) -> None:
        from practice_source_access import direct_first_write_cache_enabled

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NR2_DIRECT_FIRST_WRITE_CACHE", None)
            self.assertTrue(direct_first_write_cache_enabled())
        with patch.dict(os.environ, {"NR2_DIRECT_FIRST_WRITE_CACHE": "0"}, clear=False):
            self.assertFalse(direct_first_write_cache_enabled())


if __name__ == "__main__":
    unittest.main()

