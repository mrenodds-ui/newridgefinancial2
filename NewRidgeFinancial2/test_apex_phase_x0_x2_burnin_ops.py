"""Phase X0–X2 — burn-in ops artifacts present (Moonshot REAUDIT6)."""

from __future__ import annotations

import unittest
from pathlib import Path

from apex_backend import BUILD_ID

NR2 = Path(__file__).resolve().parent


def _repo_root() -> Path:
    cand = Path(__file__).resolve().parent
    while cand != cand.parent:
        if (cand / "scripts").is_dir() and (cand / "NewRidgeFinancial2").is_dir():
            return cand
        cand = cand.parent
    return Path(__file__).resolve().parents[1]


REPO = _repo_root()


class BurnInOpsX0X2Tests(unittest.TestCase):
    def test_build_id(self):
        self.assertEqual(BUILD_ID, "hal-10576")

    def test_runbook_and_scripts_exist(self):
        doc = NR2 / "docs" / "MOONSHOT_AI_PM_PHASE_X0_X2_APPLIED_2026-07-11.md"
        self.assertTrue(doc.is_file())
        body = doc.read_text(encoding="utf-8")
        self.assertIn("nr2_burnin_enable_flags.ps1", body)
        self.assertIn("nr2_register_scheduled_tasks.ps1", body)
        self.assertIn("validate_nr2_burnin.py", body)

        for name in (
            "nr2_burnin_enable_flags.ps1",
            "nr2_burnin_disable_flags.ps1",
            "nr2_register_scheduled_tasks.ps1",
            "nr2_unregister_scheduled_tasks.ps1",
            "validate_nr2_burnin.py",
            "run_nr2_import_cron.py",
            "run_nr2_scheduled_audit.py",
        ):
            path = REPO / "scripts" / name
            self.assertTrue(path.is_file(), msg=str(path))

    def test_enable_script_lists_flags(self):
        ps1 = (REPO / "scripts" / "nr2_burnin_enable_flags.ps1").read_text(encoding="utf-8")
        for flag in (
            "NR2_IMPORT_CRON",
            "NR2_AUDIT_CRON",
            "NR2_AI_TELEMETRY",
            "NR2_DATA_FRESHNESS",
            "NR2_EXPLAIN_CACHE",
        ):
            self.assertIn(flag, ps1)


if __name__ == "__main__":
    unittest.main()
