"""Pipeline-first import picks live bridge/aging/analytics over stale document-inbox cache."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from import_direct_pipeline import (
    dataset_mtime,
    pick_freshest_dataset,
    pipeline_first_imports_enabled,
)


class ImportDirectPipelineTests(unittest.TestCase):
    def test_pipeline_first_follows_direct_first_default(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NR2_PIPELINE_FIRST_IMPORTS", None)
            os.environ.pop("NR2_DIRECT_FIRST_IMPORTS", None)
            self.assertTrue(pipeline_first_imports_enabled())

    def test_pick_freshest_by_mtime_not_read_source(self) -> None:
        stale_cache = {
            "sourcePath": "/cache/softdent_dashboard_data.json",
            "modifiedAt": "2026-06-30T12:00:00+00:00",
            "rows": [{"provider": "Cache", "production": 1}],
            "readSource": "cache",
        }
        fresh_pipeline = {
            "sourcePath": "/upstream/softdent_bridge_latest.json",
            "modifiedAt": "2026-07-01T12:00:00+00:00",
            "rows": [{"provider": "Bridge", "production": 2}],
            "readSource": "direct",
            "sourceKind": "pipeline-dashboard",
        }
        picked = pick_freshest_dataset(stale_cache, fresh_pipeline)
        self.assertIs(picked, fresh_pipeline)

    def test_resolve_prefers_pipeline_over_stale_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            cache_dir.mkdir()
            cache_file = cache_dir / "softdent_ar_aging.csv"
            cache_file.write_text("Bucket,Amount\n0-30,999\n", encoding="utf-8")
            os.utime(cache_file, (1740000000, 1740000000))

            aging_path = Path(tmp) / "account_aging.jsonl"
            aging_path.write_text('{"practice_total": 5000}\n', encoding="utf-8")
            os.utime(aging_path, (1750000000, 1750000000))

            pipeline_ar = {
                "sourcePath": str(aging_path),
                "modifiedAt": datetime.fromtimestamp(1750000000, tz=timezone.utc).isoformat(),
                "rows": [{"Bucket": "0-30", "Amount": 5000}],
                "readSource": "direct",
                "sourceKind": "pipeline-jsonl",
            }
            cached = {
                "sourcePath": str(cache_file),
                "modifiedAt": datetime.fromtimestamp(1740000000, tz=timezone.utc).isoformat(),
                "rows": [{"Bucket": "0-30", "Amount": 999}],
                "readSource": "cache",
            }

            with patch.dict(
                os.environ,
                {"NR2_PIPELINE_FIRST_IMPORTS": "1", "NR2_DIRECT_FIRST_IMPORTS": "1"},
                clear=False,
            ):
                with patch("import_direct_pipeline.build_ar_pipeline_dataset", return_value=pipeline_ar):
                    with patch("import_loader._load_direct_sections") as mock_direct:
                        with patch("import_loader.softdent_import_dir", return_value=cache_dir):
                            from import_loader import load_import_bundle

                            mock_direct.return_value = {"softdent": {"ar": pipeline_ar}, "quickbooks": {}}
                            bundle = load_import_bundle(sync=False, deep=False)

            ar = (bundle.get("softdent") or {}).get("ar") or {}
            self.assertEqual(ar.get("readSource"), "direct")
            self.assertEqual(ar.get("sourceKind"), "pipeline-jsonl")
            self.assertEqual((ar.get("rows") or [{}])[0].get("Amount"), 5000)

    def test_dataset_mtime_uses_source_path(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as handle:
            path = Path(handle.name)
        try:
            dataset = {
                "sourcePath": str(path),
                "modifiedAt": "2020-01-01T00:00:00+00:00",
                "rows": [{"x": 1}],
            }
            self.assertGreaterEqual(dataset_mtime(dataset), path.stat().st_mtime - 1)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
