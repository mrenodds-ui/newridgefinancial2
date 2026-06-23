from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from scripts.frontend_toolchain_check import check_frontend_toolchain


DEFAULT_CI_GATES = (
    "app/tests/test_ci_route_wiring.py",
    "app/tests/test_ci_softdent_ingest_check.py",
)


def run_gate(project_root: Path, test_path: str) -> dict:
    command = [
        sys.executable,
        "-m",
        "pytest",
        test_path,
        "--rootdir",
        str(project_root),
        "-q",
    ]
    started_at = time.perf_counter()
    result = subprocess.run(
        command,
        cwd=str(project_root),
        capture_output=True,
        text=True,
        check=False,
    )
    duration_seconds = round(time.perf_counter() - started_at, 3)
    return {
        "test": test_path,
        "returncode": result.returncode,
        "passed": result.returncode == 0,
        "duration_seconds": duration_seconds,
        "stdout_tail": "\n".join((result.stdout or "").splitlines()[-10:]),
        "stderr_tail": "\n".join((result.stderr or "").splitlines()[-10:]),
    }


def build_frontend_toolchain_gate_result() -> dict:
    frontend_check = check_frontend_toolchain()
    return {
        "test": "scripts/frontend_toolchain_check.py",
        "returncode": 0 if frontend_check.available else 1,
        "passed": frontend_check.available,
        "duration_seconds": 0.0,
        "stdout_tail": frontend_check.message,
        "stderr_tail": "",
        "npm_path": frontend_check.npm_path,
        "npm_version": frontend_check.npm_version,
    }


def run_local_llm_gate(project_root: Path, required: bool) -> dict:
    report_path = project_root / "scripts" / "local_model_eval_report.json"
    command = [
        sys.executable,
        str(project_root / "scripts" / "run_local_model_evals.py"),
        "--output",
        str(report_path),
    ]
    if not required:
        command.append("--allow-skip-on-unavailable")

    started_at = time.perf_counter()
    result = subprocess.run(
        command,
        cwd=str(project_root),
        capture_output=True,
        text=True,
        check=False,
    )
    duration_seconds = round(time.perf_counter() - started_at, 3)

    report_payload = None
    if report_path.exists():
        try:
            report_payload = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report_payload = None

    skipped = bool(report_payload and report_payload.get("skipped"))
    passed = result.returncode == 0
    return {
        "test": "scripts/run_local_model_evals.py",
        "returncode": result.returncode,
        "passed": passed,
        "duration_seconds": duration_seconds,
        "stdout_tail": "\n".join((result.stdout or "").splitlines()[-10:]),
        "stderr_tail": "\n".join((result.stderr or "").splitlines()[-10:]),
        "required": required,
        "skipped": skipped,
        "report": report_payload,
    }


def build_ci_gate_report(
    project_root: Path,
    output_path: str = "scripts/ci_gate_report.json",
    *,
    skip_gates: bool = False,
    include_local_llm: bool = False,
    require_local_llm: bool = False,
) -> dict:
    report_path = Path(output_path)
    if not report_path.is_absolute():
        report_path = (project_root / report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    run_started_at = time.perf_counter()
    if skip_gates:
        results = []
    else:
        results = [build_frontend_toolchain_gate_result()]
        for gate in DEFAULT_CI_GATES:
            results.append(run_gate(project_root, gate))
        if include_local_llm or require_local_llm:
            results.append(run_gate(project_root, "app/tests/test_local_model_eval.py"))
            results.append(run_local_llm_gate(project_root, required=require_local_llm))

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
        "skip_gates": bool(skip_gates),
        "overall_pass": all(item["passed"] for item in results),
        "total_duration_seconds": round(time.perf_counter() - run_started_at, 3),
        "results": results,
    }
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    payload["report_path"] = str(report_path)
    return payload