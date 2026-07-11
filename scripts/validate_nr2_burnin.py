#!/usr/bin/env python3
"""Phase X2 — post burn-in validation (Moonshot REAUDIT6).

Runs W0–W2 gate tests and optional cron dry-runs.
Does not flip environment flags.

Examples:
  python scripts/validate_nr2_burnin.py
  python scripts/validate_nr2_burnin.py --force-cron
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NR2 = REPO / "NewRidgeFinancial2"

TESTS = [
    "NewRidgeFinancial2/test_apex_softdent_extended_w0.py",
    "NewRidgeFinancial2/test_apex_phase_w1_import_cron_dq.py",
    "NewRidgeFinancial2/test_apex_phase_w2_quarantine_ui.py",
    "NewRidgeFinancial2/test_apex_import_quarantine_u2b.py",
    "NewRidgeFinancial2/test_apex_phase_v0_burnin.py",
]


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> int:
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(REPO), env=env)
    return int(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="NR2 X2 burn-in validation")
    parser.add_argument(
        "--force-cron",
        action="store_true",
        help="Dry-run import cron + scheduled audit even if flags are OFF",
    )
    parser.add_argument("--skip-pytest", action="store_true")
    args = parser.parse_args()

    report: dict = {"ok": True, "steps": []}

    if not args.skip_pytest:
        code = run([sys.executable, "-m", "pytest", *TESTS, "-q"])
        report["steps"].append({"pytest": code})
        if code != 0:
            report["ok"] = False
            print(json.dumps(report, indent=2))
            return code

    if args.force_cron:
        env = os.environ.copy()
        # Keep process-local force paths; do not require setx for dry-run
        code_import = run(
            [sys.executable, str(REPO / "scripts" / "run_nr2_import_cron.py"), "--force"],
            env=env,
        )
        code_audit = run(
            [
                sys.executable,
                str(REPO / "scripts" / "run_nr2_scheduled_audit.py"),
                "--force",
                "--classify-only",
            ],
            env={**env, "NR2_AUDIT_CRON": "1"},
        )
        report["steps"].append({"import_cron_force": code_import, "audit_cron_force": code_audit})
        # import cron --force returns 0/1; audit with flag may return 0
        if code_import not in {0, 1} or code_audit not in {0, 1, 2}:
            report["ok"] = False

    # Presence checks for ops scripts
    required = [
        REPO / "scripts" / "nr2_burnin_enable_flags.ps1",
        REPO / "scripts" / "nr2_burnin_disable_flags.ps1",
        REPO / "scripts" / "nr2_register_scheduled_tasks.ps1",
        REPO / "scripts" / "nr2_unregister_scheduled_tasks.ps1",
        NR2 / "docs" / "MOONSHOT_AI_PM_PHASE_X0_X2_APPLIED_2026-07-11.md",
    ]
    missing = [str(p) for p in required if not p.is_file()]
    report["steps"].append({"missing_artifacts": missing})
    if missing:
        report["ok"] = False

    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
