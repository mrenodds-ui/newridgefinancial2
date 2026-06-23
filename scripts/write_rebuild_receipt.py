from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _run_command(command: list[str], cwd: Path) -> dict:
    started = time.perf_counter()
    result = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    duration = round(time.perf_counter() - started, 3)
    return {
        "command": command,
        "returncode": result.returncode,
        "duration_seconds": duration,
        "stdout_tail": "\n".join((result.stdout or "").splitlines()[-20:]),
        "stderr_tail": "\n".join((result.stderr or "").splitlines()[-20:]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run rebuild checks and write a structured rebuild receipt.")
    parser.add_argument(
        "--output",
        default="scripts/rebuild_receipt.json",
        help="Path to write rebuild receipt JSON (default: scripts/rebuild_receipt.json)",
    )
    parser.add_argument(
        "--skip-steps",
        action="store_true",
        help="Write receipt metadata without executing refresh/tests/gates steps.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    python_exe = Path(sys.executable)

    receipt_path = (project_root / args.output).resolve()
    receipt_path.parent.mkdir(parents=True, exist_ok=True)

    steps: list[dict] = []

    gates_report_path = project_root / "scripts" / "ci_gate_report.rebuild.json"
    if not args.skip_steps:
        refresh_cmd = [
            str(python_exe),
            str(project_root / "scripts" / "refresh_from_softdent_and_verify.py"),
        ]
        steps.append(_run_command(refresh_cmd, project_root))

        tests_cmd = [
            str(python_exe),
            "-m",
            "pytest",
            str(project_root / "app" / "tests"),
            "--rootdir",
            str(project_root),
            "-q",
        ]
        steps.append(_run_command(tests_cmd, project_root))

        gates_cmd = [
            str(python_exe),
            str(project_root / "scripts" / "run_ci_gates.py"),
            "--output",
            str(gates_report_path),
        ]
        steps.append(_run_command(gates_cmd, project_root))

    overall_pass = all(step.get("returncode", 1) == 0 for step in steps)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
        "skip_steps": bool(args.skip_steps),
        "overall_pass": overall_pass,
        "receipt_version": 1,
        "artifact_paths": {
            "rebuild_receipt": str(receipt_path),
            "ci_gate_report": str(gates_report_path),
        },
        "steps": steps,
    }

    receipt_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
