from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ci_gate_support import build_ci_gate_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CI gate tests and emit structured JSON diagnostics.")
    parser.add_argument(
        "--output",
        default="scripts/ci_gate_report.json",
        help="Path to write JSON report (default: scripts/ci_gate_report.json)",
    )
    parser.add_argument(
        "--skip-gates",
        action="store_true",
        help="Write report metadata without executing gate tests.",
    )
    parser.add_argument(
        "--include-local-llm",
        action="store_true",
        help="Run the local Ollama regression harness as part of CI gates.",
    )
    parser.add_argument(
        "--require-local-llm",
        action="store_true",
        help="Fail the gate if the local Ollama regression harness cannot run or does not pass.",
    )
    args = parser.parse_args()

    payload = build_ci_gate_report(
        PROJECT_ROOT,
        args.output,
        skip_gates=args.skip_gates,
        include_local_llm=args.include_local_llm or os.getenv("LOCAL_LLM_EVAL_ENABLED", "false").lower() == "true",
        require_local_llm=args.require_local_llm or os.getenv("LOCAL_LLM_EVAL_REQUIRED", "false").lower() == "true",
    )
    print(json.dumps(payload, indent=2))
    return 0 if payload["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
