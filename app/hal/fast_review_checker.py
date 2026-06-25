"""Opt-in fast structured review checker using the experimental ``fast_review`` lane.

This module is explicitly opt-in: it never routes through ``chat_second_opinion``,
never falls back to cloud models, and never targets the isolated ``:11436`` evaluator lane.
"""

from __future__ import annotations

import time
from typing import Any

from app.ai_local_config import (
    DEFAULT_EVALUATOR_BASE_URL,
    FAST_REVIEW_PROFILE_ALIASES,
    LocalAIConfigError,
    check_lane_runtime_available,
    get_fast_review_base_url,
    get_fast_review_model_name,
    get_model_for_profile_alias,
    is_fast_review_profile_alias,
    load_local_model_profile_config,
    resolve_lane_profile,
    resolve_profile_base_url,
)
from app.evaluation.client import (
    ResponseValidationError,
    generate_response_result,
    parse_json_object_response,
)
from app.hal.audit import record_hal_audit

FAST_REVIEW_PROFILE_ALIAS = "fast_review"
FAST_REVIEW_REQUIRED_KEYS = (
    "missing_data",
    "citation_issues",
    "possible_invented_facts",
    "contradictions",
    "recommended_action",
    "ready_for_human_review",
)
FAST_REVIEW_MODE = "hal9000:fast-review-check"
_EVALUATOR_LANE_MARKER = ":11436"


class FastReviewCheckerError(RuntimeError):
    """Raised when fast review configuration violates lane isolation rules."""


def assert_fast_review_lane_url(base_url: str) -> None:
    normalized = base_url.rstrip("/")
    if _EVALUATOR_LANE_MARKER in normalized or normalized == DEFAULT_EVALUATOR_BASE_URL.rstrip("/"):
        raise FastReviewCheckerError(
            f"fast_review must not target the isolated evaluator lane ({base_url})."
        )


def build_fast_review_prompt(*, source_text: str, review_task: str) -> str:
    task_label = review_task.strip() or "insurance_narrative_review"
    body = source_text.strip()
    return (
        "You are a structured insurance narrative reviewer. Review the source packet only.\n"
        "Do not invent patient identity, dollar amounts, dates, or clinical facts not present in the source.\n"
        "Missing data means unavailable or not provided — never treat missing accounts receivable as zero.\n"
        "Respond ONLY with a single JSON object (no markdown fences) using exactly these keys:\n"
        '- "missing_data": array of strings naming fields not provided in the source\n'
        '- "citation_issues": array of strings describing facts cited without source support (empty if none)\n'
        '- "possible_invented_facts": array of strings for values that appear invented (empty if none)\n'
        '- "contradictions": array of strings (empty if none)\n'
        '- "recommended_action": short string\n'
        '- "ready_for_human_review": boolean\n\n'
        f"Review task: {task_label}\n\n"
        f"Source packet:\n{body}\n"
    )


def parse_fast_review_structured_output(response_text: str) -> dict[str, Any]:
    payload = parse_json_object_response(response_text)
    missing_keys = [key for key in FAST_REVIEW_REQUIRED_KEYS if key not in payload]
    if missing_keys:
        raise ResponseValidationError(f"Missing required JSON keys: {', '.join(missing_keys)}")

    normalized: dict[str, Any] = {}
    for key in ("missing_data", "citation_issues", "possible_invented_facts", "contradictions"):
        value = payload.get(key)
        if value is None:
            normalized[key] = []
        elif isinstance(value, list):
            normalized[key] = [str(item) for item in value]
        else:
            raise ResponseValidationError(f"{key} must be an array of strings.")
    normalized["recommended_action"] = str(payload.get("recommended_action") or "").strip()
    ready = payload.get("ready_for_human_review")
    if not isinstance(ready, bool):
        raise ResponseValidationError("ready_for_human_review must be a boolean.")
    normalized["ready_for_human_review"] = ready
    return normalized


def _resolve_fast_review_target() -> dict[str, Any]:
    if FAST_REVIEW_PROFILE_ALIAS not in FAST_REVIEW_PROFILE_ALIASES:
        raise FastReviewCheckerError("fast_review profile alias is not registered.")
    base_url = resolve_profile_base_url(FAST_REVIEW_PROFILE_ALIAS)
    assert_fast_review_lane_url(base_url)
    return {
        "profile": FAST_REVIEW_PROFILE_ALIAS,
        "base_url": base_url,
        "model": get_model_for_profile_alias(FAST_REVIEW_PROFILE_ALIAS),
        "resolved_profile": resolve_lane_profile(load_local_model_profile_config(), FAST_REVIEW_PROFILE_ALIAS),
    }


def _profile_timeout_seconds(profile: dict[str, Any]) -> int:
    raw = profile.get("timeout_seconds")
    try:
        return int(raw) if raw is not None else 300
    except (TypeError, ValueError):
        return 300


def run_fast_review_check(
    *,
    source_text: str,
    review_task: str = "insurance_narrative_review",
    packet_id: str | None = None,
    actor: str = "system",
) -> dict[str, Any]:
    """Run an explicit opt-in structured review on the fast_review lane only."""

    if not is_fast_review_profile_alias(FAST_REVIEW_PROFILE_ALIAS):
        raise FastReviewCheckerError("fast_review is not a registered opt-in profile.")

    target = _resolve_fast_review_target()
    base_url = str(target["base_url"])
    model_name = str(target["model"])
    guardrails = [
        "opt-in fast_review checker only",
        "no chat_second_opinion fallback",
        "no cloud fallback",
        "no evaluator lane (:11436)",
        "structured JSON review output",
        "review before submission",
    ]

    available, lane_error = check_lane_runtime_available(FAST_REVIEW_PROFILE_ALIAS)
    if not available:
        audit_entry = record_hal_audit(
            actor=actor,
            mode=FAST_REVIEW_MODE,
            sanitized_question=(packet_id or review_task)[:180],
            retrieval_ids=[],
            response_summary="lane_unavailable",
        )
        return {
            "status": "lane_unavailable",
            "profile": FAST_REVIEW_PROFILE_ALIAS,
            "model": model_name,
            "base_url": base_url,
            "review": None,
            "raw_output": None,
            "latency_seconds": None,
            "parse_error": None,
            "error": lane_error or "fast_review lane unavailable",
            "audit_id": audit_entry["audit_id"],
            "guardrails": guardrails,
            "packet_id": packet_id,
        }

    prompt = build_fast_review_prompt(source_text=source_text, review_task=review_task)
    started = time.perf_counter()
    try:
        result = generate_response_result(
            base_url=base_url,
            profile=target["resolved_profile"],
            prompt=prompt,
            timeout_seconds=_profile_timeout_seconds(target["resolved_profile"]),
            seed=target["resolved_profile"].get("seed"),
        )
    except LocalAIConfigError as exc:
        audit_entry = record_hal_audit(
            actor=actor,
            mode=FAST_REVIEW_MODE,
            sanitized_question=(packet_id or review_task)[:180],
            retrieval_ids=[],
            response_summary="error",
        )
        return {
            "status": "error",
            "profile": FAST_REVIEW_PROFILE_ALIAS,
            "model": model_name,
            "base_url": base_url,
            "review": None,
            "raw_output": None,
            "latency_seconds": round(time.perf_counter() - started, 4),
            "parse_error": None,
            "error": str(exc),
            "audit_id": audit_entry["audit_id"],
            "guardrails": guardrails,
            "packet_id": packet_id,
        }
    except Exception as exc:  # noqa: BLE001 - surface runtime failures without fallback
        audit_entry = record_hal_audit(
            actor=actor,
            mode=FAST_REVIEW_MODE,
            sanitized_question=(packet_id or review_task)[:180],
            retrieval_ids=[],
            response_summary="error",
        )
        return {
            "status": "error",
            "profile": FAST_REVIEW_PROFILE_ALIAS,
            "model": model_name,
            "base_url": base_url,
            "review": None,
            "raw_output": None,
            "latency_seconds": round(time.perf_counter() - started, 4),
            "parse_error": None,
            "error": str(exc),
            "audit_id": audit_entry["audit_id"],
            "guardrails": guardrails,
            "packet_id": packet_id,
        }

    raw_output = str(result.get("response_text") or "")
    latency_seconds = round(time.perf_counter() - started, 4)
    try:
        review = parse_fast_review_structured_output(raw_output)
    except ResponseValidationError as exc:
        audit_entry = record_hal_audit(
            actor=actor,
            mode=FAST_REVIEW_MODE,
            sanitized_question=(packet_id or review_task)[:180],
            retrieval_ids=[],
            response_summary="parse_error",
        )
        return {
            "status": "parse_error",
            "profile": FAST_REVIEW_PROFILE_ALIAS,
            "model": model_name,
            "base_url": base_url,
            "review": None,
            "raw_output": raw_output,
            "latency_seconds": latency_seconds,
            "parse_error": str(exc),
            "error": None,
            "audit_id": audit_entry["audit_id"],
            "guardrails": guardrails,
            "packet_id": packet_id,
        }

    audit_entry = record_hal_audit(
        actor=actor,
        mode=FAST_REVIEW_MODE,
        sanitized_question=(packet_id or review_task)[:180],
        retrieval_ids=[],
        response_summary=str(review.get("recommended_action") or "")[:180],
    )
    return {
        "status": "ok",
        "profile": FAST_REVIEW_PROFILE_ALIAS,
        "model": model_name,
        "base_url": base_url,
        "review": review,
        "raw_output": raw_output,
        "latency_seconds": latency_seconds,
        "parse_error": None,
        "error": None,
        "audit_id": audit_entry["audit_id"],
        "guardrails": guardrails,
        "packet_id": packet_id,
    }
