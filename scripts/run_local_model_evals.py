from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.evaluation.client import check_ollama_available, load_json_file
from app.evaluation.engine import run_assertion_cases, run_judge_cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic local-model regression evaluations against Ollama.")
    parser.add_argument("--config", default="evals/local_model_profiles.json")
    parser.add_argument("--dataset", default="evals/golden_dataset.json")
    parser.add_argument("--output", default="scripts/local_model_eval_report.json")
    parser.add_argument("--base-url", default=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-skip-on-unavailable", action="store_true")
    args = parser.parse_args()

    project_root = PROJECT_ROOT
    config = load_json_file(project_root / args.config)
    dataset = load_json_file(project_root / args.dataset)

    if not args.dry_run:
        available, error_message = check_ollama_available(args.base_url, timeout_seconds=10)
        if not available:
            payload = {
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "base_url": args.base_url,
                "dry_run": False,
                "overall_pass": False,
                "skipped": bool(args.allow_skip_on_unavailable),
                "reason": f"ollama_unavailable: {error_message}",
                "result_count": 0,
                "results": [],
            }
            output_path = (project_root / args.output).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(json.dumps(payload, indent=2))
            return 0 if args.allow_skip_on_unavailable else 1

    assertion_results = run_assertion_cases(dataset, config, args.base_url, args.timeout_seconds, args.dry_run)
    judge_results = run_judge_cases(dataset, config, args.base_url, args.timeout_seconds, args.dry_run)
    all_results = assertion_results + judge_results
    overall_pass = all(item.get("passed", False) for item in all_results) if all_results else True

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "dry_run": bool(args.dry_run),
        "overall_pass": overall_pass,
        "result_count": len(all_results),
        "results": all_results,
    }

    output_path = (project_root / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())