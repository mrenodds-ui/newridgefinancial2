"""Run focused manifest/checksum import tests and persist the result."""

from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path


TEST_MODULES = [
    "test_import_cache_ttl",
    "test_import_diagnostics_checksums",
]


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    output_path = repo_root / "data" / "import_manifest_checksum_slice_validation.json"
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    started_at = time.time()
    try:
        suite = unittest.TestSuite()
        loader = unittest.defaultTestLoader
        for module_name in TEST_MODULES:
            suite.addTests(loader.loadTestsFromName(module_name))
        result = unittest.TestResult()
        suite.run(result)
        payload = {
            "ok": result.wasSuccessful(),
            "modules": TEST_MODULES,
            "testsRun": result.testsRun,
            "failures": [
                {"test": str(test_case), "details": details}
                for test_case, details in result.failures
            ],
            "errors": [
                {"test": str(test_case), "details": details}
                for test_case, details in result.errors
            ],
            "skipped": [
                {"test": str(test_case), "reason": reason}
                for test_case, reason in result.skipped
            ],
            "durationSec": round(time.time() - started_at, 3),
        }
    except Exception as exc:
        payload = {
            "ok": False,
            "modules": TEST_MODULES,
            "testsRun": 0,
            "failures": [],
            "errors": [{"test": "loader", "details": repr(exc)}],
            "skipped": [],
            "durationSec": round(time.time() - started_at, 3),
        }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
