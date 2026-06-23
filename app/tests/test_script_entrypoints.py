from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def test_run_ci_gates_skip_mode_writes_report(tmp_path: Path):
    report_path = tmp_path / "ci_gate_report.json"

    result = _run_script("scripts/run_ci_gates.py", "--skip-gates", "--output", str(report_path))

    assert result.returncode == 0, result.stderr
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["skip_gates"] is True
    assert payload["overall_pass"] is True
    assert payload["results"] == []


def test_write_rebuild_receipt_skip_mode_writes_receipt(tmp_path: Path):
    receipt_path = tmp_path / "rebuild_receipt.json"

    result = _run_script("scripts/write_rebuild_receipt.py", "--skip-steps", "--output", str(receipt_path))

    assert result.returncode == 0, result.stderr
    assert receipt_path.exists()
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["skip_steps"] is True
    assert payload["overall_pass"] is True
    assert payload["steps"] == []