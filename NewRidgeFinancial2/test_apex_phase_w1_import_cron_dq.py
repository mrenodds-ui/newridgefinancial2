"""Phase W1 — import cron + DQ validation gates."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

from apex_backend import BUILD_ID, build_apex_widgets
from apex_import_dq_pack import GAP_DQ_BLOCKED, dq_enabled, validate_bundle_dq
from apex_import_scheduler_pack import import_cron_enabled, run_import_cron_once
from apex_unified_db_pack import ingest_from_bundle


class ImportCronDqW1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self._tmpdir.name)
        self.db_path = self.root / "nr2_unified_w1.db"
        self._prev = {
            "NR2_IMPORT_CRON": os.environ.get("NR2_IMPORT_CRON"),
            "NR2_IMPORT_DQ": os.environ.get("NR2_IMPORT_DQ"),
            "NR2_IMPORT_CRON_LOG": os.environ.get("NR2_IMPORT_CRON_LOG"),
            "NR2_IMPORT_POLL_STATE": os.environ.get("NR2_IMPORT_POLL_STATE"),
        }
        os.environ["NR2_IMPORT_CRON_LOG"] = str(self.root / "cron.jsonl")
        os.environ["NR2_IMPORT_POLL_STATE"] = str(self.root / "poll_state.json")

    def tearDown(self) -> None:
        for key, prev in self._prev.items():
            if prev is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prev
        try:
            self._tmpdir.cleanup()
        except Exception:
            pass

    def test_build_id(self):
        self.assertEqual(BUILD_ID, "hal-10492")

    def test_dq_default_on_cron_default_off(self):
        os.environ.pop("NR2_IMPORT_DQ", None)
        os.environ.pop("NR2_IMPORT_CRON", None)
        self.assertTrue(dq_enabled())
        self.assertFalse(import_cron_enabled())

    def test_dq_blocks_negative_production(self):
        os.environ["NR2_IMPORT_DQ"] = "1"
        bad = {
            "softdent": {
                "dashboard": {
                    "rows": [{"period": "2026-06", "production": -100, "collections": 50}]
                }
            }
        }
        dq = validate_bundle_dq(bad)
        self.assertFalse(dq.get("ok"))
        self.assertEqual(dq.get("gapCode"), GAP_DQ_BLOCKED)
        rules = {v.get("rule") for v in (dq.get("violations") or [])}
        self.assertIn("no_negative_production", rules)

        blocked = ingest_from_bundle(bad, db_path=self.db_path)
        self.assertFalse(blocked.get("ok"))
        self.assertEqual(blocked.get("reason"), "dq_blocked")

        ok = ingest_from_bundle(
            {
                "softdent": {
                    "dashboard": {
                        "rows": [
                            {
                                "period": "2026-06",
                                "production": 1000,
                                "collections": 800,
                                "collectionsPending": False,
                            }
                        ]
                    }
                }
            },
            db_path=self.db_path,
        )
        self.assertTrue(ok.get("ok"))

    def test_dq_future_period(self):
        os.environ["NR2_IMPORT_DQ"] = "1"
        dq = validate_bundle_dq(
            {
                "softdent": {
                    "dashboard": {
                        "rows": [{"period": "2099-01", "production": 10, "collections": 10}]
                    }
                }
            },
            today=date(2026, 7, 11),
        )
        self.assertFalse(dq.get("ok"))
        self.assertTrue(
            any(v.get("rule") == "no_future_dates" for v in (dq.get("violations") or []))
        )

    def test_dq_skip_bypass(self):
        os.environ["NR2_IMPORT_DQ"] = "1"
        bad = {
            "softdent": {
                "dashboard": {"rows": [{"period": "2026-06", "production": -1, "collections": 0}]}
            }
        }
        out = ingest_from_bundle(bad, db_path=self.db_path, skip_dq=True)
        self.assertTrue(out.get("ok"))

    def test_cron_disabled_exit(self):
        os.environ.pop("NR2_IMPORT_CRON", None)
        out = run_import_cron_once(force=False)
        log = out if "reason" in out else out.get("log")
        self.assertEqual(log.get("reason"), "import_cron_disabled")
        self.assertEqual(log.get("exit"), 2)

    def test_cron_cli_disabled(self):
        env = os.environ.copy()
        env.pop("NR2_IMPORT_CRON", None)
        env["NR2_IMPORT_CRON_LOG"] = str(self.root / "cli_cron.jsonl")
        repo = Path(__file__).resolve().parents[1]
        script = repo / "scripts" / "run_nr2_import_cron.py"
        # test lives in NewRidgeFinancial2/ — scripts at repo root
        if not script.is_file():
            repo = Path(__file__).resolve().parents[1].parent
            script = repo / "scripts" / "run_nr2_import_cron.py"
        # Prefer workspace root that contains both NewRidgeFinancial2 and scripts
        cand = Path(__file__).resolve().parent
        while cand != cand.parent:
            if (cand / "scripts" / "run_nr2_import_cron.py").is_file() and (cand / "NewRidgeFinancial2").is_dir():
                repo = cand
                script = cand / "scripts" / "run_nr2_import_cron.py"
                break
            cand = cand.parent
        self.assertTrue(script.is_file(), msg=str(script))
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(repo),
            env=env,
            capture_output=True,
            text=True,
        )
        combined = (proc.stdout or "") + (proc.stderr or "")
        self.assertEqual(proc.returncode, 2, msg=combined)
        self.assertIn("import_cron_disabled", combined)

    def test_widgets(self):
        os.environ["NR2_IMPORT_DQ"] = "1"
        os.environ.pop("NR2_IMPORT_CRON", None)
        out = build_apex_widgets("financial")
        ids = {w.get("id") for w in (out.get("widgets") or []) if isinstance(w, dict)}
        self.assertIn("import-dq-status", ids)
        self.assertIn("import-cron-status", ids)


if __name__ == "__main__":
    unittest.main()
