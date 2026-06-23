from __future__ import annotations

from pathlib import Path

from scripts import ci_gate_support
from scripts.frontend_toolchain_check import FrontendToolchainCheckResult


def test_build_ci_gate_report_skip_mode_writes_report(tmp_path: Path):
    report_path = tmp_path / "ci_gate_report.json"

    payload = ci_gate_support.build_ci_gate_report(tmp_path, str(report_path), skip_gates=True)

    assert report_path.exists()
    assert payload["skip_gates"] is True
    assert payload["overall_pass"] is True
    assert payload["results"] == []


def test_build_ci_gate_report_uses_canonical_gate_list(tmp_path: Path, monkeypatch):
    recorded_gates: list[str] = []

    monkeypatch.setattr(
        ci_gate_support,
        "check_frontend_toolchain",
        lambda: FrontendToolchainCheckResult(
            available=True,
            npm_path="C:/Program Files/nodejs/npm.CMD",
            npm_version="11.13.0",
            message="npm is available at C:/Program Files/nodejs/npm.CMD.",
        ),
    )

    def fake_run_gate(project_root: Path, test_path: str) -> dict:
        recorded_gates.append(test_path)
        return {
            "test": test_path,
            "returncode": 0,
            "passed": True,
            "duration_seconds": 0.0,
            "stdout_tail": "ok",
            "stderr_tail": "",
        }

    monkeypatch.setattr(ci_gate_support, "run_gate", fake_run_gate)

    payload = ci_gate_support.build_ci_gate_report(tmp_path, skip_gates=False)

    assert recorded_gates == list(ci_gate_support.DEFAULT_CI_GATES)
    assert payload["overall_pass"] is True
    assert payload["results"][0]["test"] == "scripts/frontend_toolchain_check.py"