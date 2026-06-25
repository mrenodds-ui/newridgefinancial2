from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ai_local_config import resolve_ab_eval_lane, resolve_profile_base_url
from app.evaluation.ab_compare import run_ab_comparison, validate_ab_prompt_cases
from app.evaluation.client import check_ollama_available, load_json_file


def emit_progress(message: str, *, started_at: float) -> None:
    elapsed_seconds = perf_counter() - started_at
    print(f"[ab-eval +{elapsed_seconds:0.1f}s] {message}", file=sys.stderr, flush=True)


def _resolve_lane_base_urls(profile_a: str, profile_b: str, override_base_url: str) -> tuple[str, str]:
    return (
        resolve_profile_base_url(profile_a, override_base_url=override_base_url),
        resolve_profile_base_url(profile_b, override_base_url=override_base_url),
    )


def _resolve_lane_targets(
    config: dict[str, object],
    profile_a: str,
    profile_b: str,
    override_base_url: str,
) -> tuple[dict[str, object], dict[str, object]]:
    return (
        resolve_ab_eval_lane(config, profile_a, override_base_url=override_base_url),
        resolve_ab_eval_lane(config, profile_b, override_base_url=override_base_url),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run side-by-side local-model A/B comparisons against Ollama. "
            "Each profile resolves to its configured lane URL unless --base-url overrides both."
        )
    )
    parser.add_argument("--config", default="evals/local_model_profiles.json")
    parser.add_argument("--prompts", default="evals/hal_humanization_ab_prompts.json")
    parser.add_argument("--output", default="scripts/local_model_ab_report.json")
    parser.add_argument("--profile-a", default="chat")
    parser.add_argument("--profile-b", default="chat_second_opinion")
    parser.add_argument(
        "--base-url",
        default="",
        help=(
            "Optional CLI override applied to both profiles. "
            "When omitted, each profile uses its lane URL from ai_local_config."
        ),
    )
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--max-ttft", type=float, default=0.75)
    parser.add_argument("--max-tps-drop", type=float, default=0.15)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = load_json_file(PROJECT_ROOT / args.config)
    prompts = validate_ab_prompt_cases(load_json_file(PROJECT_ROOT / args.prompts))
    lane_a, lane_b = _resolve_lane_targets(config, args.profile_a, args.profile_b, args.base_url)
    profile_a_base_url = str(lane_a["base_url"])
    profile_b_base_url = str(lane_b["base_url"])

    if not args.dry_run:
        lane_checks = {
            args.profile_a: profile_a_base_url,
            args.profile_b: profile_b_base_url,
        }
        for profile_alias, lane_base_url in lane_checks.items():
            available, error_message = check_ollama_available(lane_base_url, timeout_seconds=10)
            if not available:
                payload = {
                    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                    "base_url": lane_base_url,
                    "profile": profile_alias,
                    "overall_pass": False,
                    "reason": f"ollama_unavailable: {error_message}",
                    "prompt_count": 0,
                    "cases": [],
                }
                output_path = (PROJECT_ROOT / args.output).resolve()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                print(json.dumps(payload, indent=2))
                return 1

    started_at = perf_counter()
    emit_progress(
        (
            f"loaded prompts={len(prompts)} profile_a={args.profile_a}@{profile_a_base_url} "
            f"model={lane_a['model']} profile_b={args.profile_b}@{profile_b_base_url} "
            f"model={lane_b['model']} dry_run={bool(args.dry_run)}"
        ),
        started_at=started_at,
    )

    comparison = run_ab_comparison(
        prompts=prompts,
        config=config,
        base_url=profile_a_base_url,
        profile_a_base_url=profile_a_base_url,
        profile_b_base_url=profile_b_base_url,
        timeout_seconds=args.timeout_seconds,
        profile_a_alias=args.profile_a,
        profile_b_alias=args.profile_b,
        max_ttft_seconds=args.max_ttft,
        max_tps_drop_fraction=args.max_tps_drop,
        dry_run=bool(args.dry_run),
        progress_callback=lambda message: emit_progress(message, started_at=started_at),
    )
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": profile_a_base_url,
        "profile_base_urls": {
            args.profile_a: profile_a_base_url,
            args.profile_b: profile_b_base_url,
        },
        "profile_models": {
            args.profile_a: lane_a["model"],
            args.profile_b: lane_b["model"],
        },
        "dry_run": bool(args.dry_run),
        **comparison,
    }

    output_path = (PROJECT_ROOT / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if args.dry_run:
        return 0
    return 1 if payload.get("regression_flags", {}).get("any_failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
