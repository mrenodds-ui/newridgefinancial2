"""Local-only bakeoff harness comparing the backend second-opinion lane against the
experimental fast_review lane on de-identified insurance narrative review packets.

This script is manual and local-only. It:
  * loads de-identified packet JSON files (no PHI)
  * resolves each profile to its lane URL via app.ai_local_config (explicit resolution)
  * never targets the :11436 evaluator lane
  * never falls back to cloud models
  * records lane availability instead of treating a down lane as pass/fail
  * writes a machine-readable JSON report (default output is gitignored)

It does NOT replace chat_second_opinion and does NOT wire fast_review into any
user-facing narrative generation path.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ai_local_config import (
    DEFAULT_EVALUATOR_BASE_URL,
    get_model_for_profile_alias,
    resolve_lane_profile,
    resolve_profile_base_url,
)
from app.evaluation.client import (
    check_ollama_available,
    generate_response_result,
    load_json_file,
    parse_json_object_response,
)

DEFAULT_PACKET_DIR = "evals/insurance_narrative_packets"
DEFAULT_PROFILE_CONFIG = "evals/local_model_profiles.json"
DEFAULT_PROFILES = ("chat_second_opinion", "fast_review")
DEFAULT_OUTPUT = "fast_review_bakeoff_report.json"

_EVALUATOR_LANE_MARKER = ":11436"
_NUMBER_PATTERN = re.compile(r"\$?\d[\d,]*(?:\.\d+)?")


class BakeoffLaneError(RuntimeError):
    """Raised when a profile would resolve to a forbidden lane."""


def assert_not_evaluator_lane(profile_alias: str, base_url: str) -> None:
    if _EVALUATOR_LANE_MARKER in base_url or base_url.rstrip("/") == DEFAULT_EVALUATOR_BASE_URL.rstrip("/"):
        raise BakeoffLaneError(
            f"Profile {profile_alias!r} resolved to the isolated 235B evaluator lane "
            f"({base_url}); the bakeoff harness must never use {_EVALUATOR_LANE_MARKER}."
        )


def resolve_bakeoff_target(config: dict[str, Any], profile_alias: str) -> dict[str, Any]:
    base_url = resolve_profile_base_url(profile_alias)
    assert_not_evaluator_lane(profile_alias, base_url)
    return {
        "profile": profile_alias,
        "base_url": base_url,
        "model": get_model_for_profile_alias(profile_alias),
        "resolved_profile": resolve_lane_profile(config, profile_alias),
    }


def load_packets(packet_dir: Path) -> list[dict[str, Any]]:
    packets: list[dict[str, Any]] = []
    for packet_path in sorted(packet_dir.glob("*.json")):
        payload = load_json_file(packet_path)
        if not isinstance(payload, dict):
            continue
        payload.setdefault("id", packet_path.stem)
        payload["_source_path"] = str(packet_path.relative_to(PROJECT_ROOT)) if packet_path.is_relative_to(PROJECT_ROOT) else str(packet_path)
        packets.append(payload)
    return packets


def build_review_prompt(packet: dict[str, Any]) -> str:
    instructions = str(packet.get("review_instructions") or "").strip()
    source_text = str(packet.get("source_text") or "").strip()
    return f"{instructions}\n\nSource packet:\n{source_text}\n"


def _normalize_tokens(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _extract_number_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for match in _NUMBER_PATTERN.findall(text or ""):
        cleaned = match.lstrip("$").replace(",", "").strip()
        if cleaned:
            tokens.append(cleaned)
    return tokens


def score_review_output(packet: dict[str, Any], output_text: str) -> dict[str, Any]:
    """Deterministic, model-free scoring of a review output string."""

    lowered = (output_text or "").lower()

    parsed_payload: dict[str, Any] | None = None
    json_parsed = False
    required_keys = _normalize_tokens(packet.get("required_json_keys"))
    missing_required_keys: list[str] = list(required_keys)
    try:
        parsed_payload = parse_json_object_response(output_text or "")
        json_parsed = True
        missing_required_keys = [key for key in required_keys if key not in parsed_payload]
    except Exception:
        json_parsed = False

    expected_missing = _normalize_tokens(packet.get("expected_missing_data"))
    detected_missing = [item for item in expected_missing if item.lower() in lowered]

    source_citations = _normalize_tokens(packet.get("source_citations"))
    matched_citations = [item for item in source_citations if item.lower() in lowered]

    allowed_numbers = {token for token in _normalize_tokens(packet.get("allowed_numbers"))}
    output_numbers = _extract_number_tokens(output_text or "")
    invented_number_tokens = sorted({token for token in output_numbers if token not in allowed_numbers})

    return {
        "output_length_chars": len(output_text or ""),
        "json_structured": {
            "parsed": json_parsed,
            "required_keys": required_keys,
            "missing_required_keys": missing_required_keys,
            "has_all_required_keys": json_parsed and not missing_required_keys,
        },
        "missing_data_detection": {
            "expected": expected_missing,
            "detected": detected_missing,
            "detected_count": len(detected_missing),
            "expected_count": len(expected_missing),
            "all_detected": bool(expected_missing) and len(detected_missing) == len(expected_missing),
        },
        "citation_compliance": {
            "source_citations": source_citations,
            "matched": matched_citations,
            "matched_count": len(matched_citations),
            "source_count": len(source_citations),
        },
        "invented_fact_warnings": {
            "candidate_count": len(invented_number_tokens),
            "candidate_number_tokens": invented_number_tokens,
            "note": "Heuristic: numeric tokens in output not present in packet allowed_numbers.",
        },
    }


def run_packet_for_target(
    *,
    packet: dict[str, Any],
    target: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    prompt = build_review_prompt(packet)
    started = perf_counter()
    try:
        result = generate_response_result(
            base_url=target["base_url"],
            profile=target["resolved_profile"],
            prompt=prompt,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001 - record any runtime failure, keep going
        return {
            "packet_id": packet.get("id"),
            "profile": target["profile"],
            "model": target["model"],
            "base_url": target["base_url"],
            "status": "error",
            "error": str(exc),
            "latency_seconds": round(perf_counter() - started, 4),
        }

    output_text = str(result.get("response_text") or "")
    return {
        "packet_id": packet.get("id"),
        "profile": target["profile"],
        "model": target["model"],
        "base_url": target["base_url"],
        "status": "ok",
        "latency_seconds": round(perf_counter() - started, 4),
        "scores": score_review_output(packet, output_text),
        "ollama_metrics": result.get("metrics"),
        "output_text": output_text,
    }


def build_report(
    *,
    packets: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    lane_availability: dict[str, dict[str, Any]],
    results: list[dict[str, Any]],
    dry_run: bool,
) -> dict[str, Any]:
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "profiles": [
            {
                "profile": target["profile"],
                "model": target["model"],
                "base_url": target["base_url"],
                "lane_available": lane_availability.get(target["profile"], {}).get("available"),
                "lane_error": lane_availability.get(target["profile"], {}).get("error"),
            }
            for target in targets
        ],
        "packet_ids": [packet.get("id") for packet in packets],
        "packet_count": len(packets),
        "result_count": len(results),
        "results": results,
    }


def write_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Local-only bakeoff comparing chat_second_opinion (:11435/qwen3:14b) against the "
            "experimental fast_review lane (:11437/Qwen3-Coder-30B-A3B-Instruct) on de-identified "
            "insurance narrative review packets. Never uses the :11436 evaluator lane or cloud models."
        )
    )
    parser.add_argument("--packets", default=DEFAULT_PACKET_DIR, help="Directory of de-identified packet JSON files.")
    parser.add_argument("--config", default=DEFAULT_PROFILE_CONFIG, help="Local model profile config path.")
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=list(DEFAULT_PROFILES),
        help="Profile aliases to compare (default: chat_second_opinion fast_review).",
    )
    parser.add_argument("--out", default=DEFAULT_OUTPUT, help="JSON report output path (default is gitignored).")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve lanes, load packets, and verify lane health without calling models.",
    )
    args = parser.parse_args(argv)

    config = load_json_file(PROJECT_ROOT / args.config)
    packet_dir = (PROJECT_ROOT / args.packets) if not Path(args.packets).is_absolute() else Path(args.packets)
    packets = load_packets(packet_dir)

    targets: list[dict[str, Any]] = []
    for profile_alias in args.profiles:
        targets.append(resolve_bakeoff_target(config, profile_alias))

    lane_availability: dict[str, dict[str, Any]] = {}
    for target in targets:
        available, error_message = check_ollama_available(target["base_url"], timeout_seconds=10)
        lane_availability[target["profile"]] = {"available": available, "error": error_message}

    results: list[dict[str, Any]] = []
    if not args.dry_run:
        for packet in packets:
            for target in targets:
                if not lane_availability.get(target["profile"], {}).get("available"):
                    results.append(
                        {
                            "packet_id": packet.get("id"),
                            "profile": target["profile"],
                            "model": target["model"],
                            "base_url": target["base_url"],
                            "status": "lane_unavailable",
                            "error": lane_availability.get(target["profile"], {}).get("error"),
                        }
                    )
                    continue
                results.append(
                    run_packet_for_target(
                        packet=packet,
                        target=target,
                        timeout_seconds=args.timeout_seconds,
                    )
                )

    report = build_report(
        packets=packets,
        targets=targets,
        lane_availability=lane_availability,
        results=results,
        dry_run=bool(args.dry_run),
    )

    output_path = (PROJECT_ROOT / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    write_report(report, output_path)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
