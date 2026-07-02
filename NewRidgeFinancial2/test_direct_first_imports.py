"""Direct-first import mode reads upstream exports before document-inbox cache."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from import_loader import direct_first_imports_enabled, load_import_bundle


class DirectFirstImportTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
