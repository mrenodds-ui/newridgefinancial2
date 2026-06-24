from __future__ import annotations

from collections.abc import Sequence
import re
from statistics import median
from typing import Callable
from typing import Any

from app.hal.orchestrator import get_hal_operating_picture

from .client import generate_response_result, resolve_profile


_PROTECTED_PERIOD_TOKEN = "<DOT>"
_ABBREVIATION_PATTERN = re.compile(r"\b(?:e\.g\.|i\.e\.|vs\.|Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.|Sr\.|Jr\.)")
_DECIMAL_PATTERN = re.compile(r"(?<=\d)\.(?=\d)")
_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'`(\[])|(?<=[.!?])$")
_VERIFIED_CONTEXT_MARKERS = (
    "operating picture",
    "what matters most this morning",
    "what matters this morning",
)


def count_paragraphs(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    return len([paragraph for paragraph in stripped.split("\n\n") if paragraph.strip()])


def count_sentences(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0

    protected = _ABBREVIATION_PATTERN.sub(lambda match: match.group(0).replace(".", _PROTECTED_PERIOD_TOKEN), stripped)
    protected = _DECIMAL_PATTERN.sub(_PROTECTED_PERIOD_TOKEN, protected)
    sentences = [segment.strip() for segment in _SENTENCE_SPLIT_PATTERN.split(protected) if segment.strip()]
    if not sentences:
        return 0
    return len(sentences)


def summarize_output(text: str) -> dict[str, int | float]:
    stripped = text.strip()
    if not stripped:
        return {
            "character_count": 0,
            "word_count": 0,
            "sentence_count": 0,
            "paragraph_count": 0,
            "avg_words_per_sentence": 0.0,
        }

    words = [word for word in stripped.replace("\n", " ").split(" ") if word]
    paragraph_count = count_paragraphs(stripped)
    sentence_count = max(count_sentences(stripped), 1)
    return {
        "character_count": len(stripped),
        "word_count": len(words),
        "sentence_count": sentence_count,
        "paragraph_count": paragraph_count,
        "avg_words_per_sentence": round(len(words) / sentence_count, 2),
    }


def _median_or_none(values: list[float | int | None]) -> float | None:
    numeric_values = [float(value) for value in values if value is not None]
    if not numeric_values:
        return None
    return round(float(median(numeric_values)), 4)


def _average_or_none(values: list[float | int]) -> float | None:
    if not values:
        return None
    return round(float(sum(values) / len(values)), 2)


def _delta_or_none(*, baseline: float | int | None, candidate: float | int | None, digits: int = 4) -> float | None:
    if baseline is None or candidate is None:
        return None
    return round(float(candidate) - float(baseline), digits)


def build_profile_summary(*, cases: Sequence[dict[str, object]], profile_key: str) -> dict[str, object]:
    profile_cases = [case[profile_key] for case in cases if isinstance(case.get(profile_key), dict)]
    if not profile_cases:
        return {
            "case_count": 0,
            "median_ttft_estimate_seconds": None,
            "median_output_tokens_per_second": None,
            "median_end_to_end_tokens_per_second": None,
            "average_word_count": None,
            "average_character_count": None,
            "median_sentence_count": None,
            "median_paragraph_count": None,
        }

    ttft_values = [
        profile_case.get("performance", {}).get("time_to_first_token_estimate_seconds")
        for profile_case in profile_cases
        if isinstance(profile_case.get("performance"), dict)
    ]
    output_tps_values = [
        profile_case.get("performance", {}).get("output_tokens_per_second")
        for profile_case in profile_cases
        if isinstance(profile_case.get("performance"), dict)
    ]
    end_to_end_tps_values = [
        profile_case.get("performance", {}).get("end_to_end_tokens_per_second")
        for profile_case in profile_cases
        if isinstance(profile_case.get("performance"), dict)
    ]
    word_counts = [
        int(profile_case.get("summary", {}).get("word_count") or 0)
        for profile_case in profile_cases
        if isinstance(profile_case.get("summary"), dict)
    ]
    character_counts = [
        int(profile_case.get("summary", {}).get("character_count") or 0)
        for profile_case in profile_cases
        if isinstance(profile_case.get("summary"), dict)
    ]
    sentence_counts = [
        int(profile_case.get("summary", {}).get("sentence_count") or 0)
        for profile_case in profile_cases
        if isinstance(profile_case.get("summary"), dict)
    ]
    paragraph_counts = [
        int(profile_case.get("summary", {}).get("paragraph_count") or 0)
        for profile_case in profile_cases
        if isinstance(profile_case.get("summary"), dict)
    ]

    return {
        "case_count": len(profile_cases),
        "median_ttft_estimate_seconds": _median_or_none(ttft_values),
        "median_output_tokens_per_second": _median_or_none(output_tps_values),
        "median_end_to_end_tokens_per_second": _median_or_none(end_to_end_tps_values),
        "average_word_count": _average_or_none(word_counts),
        "average_character_count": _average_or_none(character_counts),
        "median_sentence_count": _median_or_none(sentence_counts),
        "median_paragraph_count": _median_or_none(paragraph_counts),
    }


def build_profile_delta(
    *,
    baseline_alias: str,
    baseline_summary: dict[str, object],
    candidate_alias: str,
    candidate_summary: dict[str, object],
) -> dict[str, object]:
    return {
        "baseline_alias": baseline_alias,
        "candidate_alias": candidate_alias,
        "candidate_minus_baseline": {
            "median_ttft_estimate_seconds": _delta_or_none(
                baseline=baseline_summary.get("median_ttft_estimate_seconds"),
                candidate=candidate_summary.get("median_ttft_estimate_seconds"),
            ),
            "median_output_tokens_per_second": _delta_or_none(
                baseline=baseline_summary.get("median_output_tokens_per_second"),
                candidate=candidate_summary.get("median_output_tokens_per_second"),
            ),
            "median_end_to_end_tokens_per_second": _delta_or_none(
                baseline=baseline_summary.get("median_end_to_end_tokens_per_second"),
                candidate=candidate_summary.get("median_end_to_end_tokens_per_second"),
            ),
            "average_word_count": _delta_or_none(
                baseline=baseline_summary.get("average_word_count"),
                candidate=candidate_summary.get("average_word_count"),
                digits=2,
            ),
            "average_character_count": _delta_or_none(
                baseline=baseline_summary.get("average_character_count"),
                candidate=candidate_summary.get("average_character_count"),
                digits=2,
            ),
            "median_sentence_count": _delta_or_none(
                baseline=baseline_summary.get("median_sentence_count"),
                candidate=candidate_summary.get("median_sentence_count"),
                digits=2,
            ),
            "median_paragraph_count": _delta_or_none(
                baseline=baseline_summary.get("median_paragraph_count"),
                candidate=candidate_summary.get("median_paragraph_count"),
                digits=2,
            ),
        },
    }


def build_regression_flags(
    *,
    baseline_summary: dict[str, object],
    candidate_summary: dict[str, object],
    max_ttft_seconds: float,
    max_tps_drop_fraction: float,
    gate_evaluated: bool,
) -> dict[str, object]:
    if not gate_evaluated:
        return {
            "gate_evaluated": False,
            "gate_skipped": True,
            "any_failed": False,
            "output_tps_regressed": False,
            "ttft_ceiling_exceeded": False,
            "gate_reason": "Gate evaluation skipped because the run was executed in dry-run mode.",
        }

    baseline_tps = baseline_summary.get("median_output_tokens_per_second")
    candidate_tps = candidate_summary.get("median_output_tokens_per_second")
    candidate_ttft = candidate_summary.get("median_ttft_estimate_seconds")

    output_tps_regressed = False
    if isinstance(baseline_tps, (int, float)) and baseline_tps > 0 and isinstance(candidate_tps, (int, float)):
        min_allowed_tps = float(baseline_tps) * (1 - max_tps_drop_fraction)
        output_tps_regressed = float(candidate_tps) < min_allowed_tps

    ttft_ceiling_exceeded = False
    if isinstance(candidate_ttft, (int, float)):
        ttft_ceiling_exceeded = float(candidate_ttft) > max_ttft_seconds

    any_failed = output_tps_regressed or ttft_ceiling_exceeded
    reasons: list[str] = []
    if ttft_ceiling_exceeded and isinstance(candidate_ttft, (int, float)):
        reasons.append(
            f"Candidate median TTFT ({float(candidate_ttft):.3f}s) exceeded absolute ceiling of {max_ttft_seconds:.3f}s."
        )
    if output_tps_regressed and isinstance(baseline_tps, (int, float)) and baseline_tps > 0 and isinstance(candidate_tps, (int, float)):
        tps_droop = (float(baseline_tps) - float(candidate_tps)) / float(baseline_tps)
        reasons.append(
            "Candidate median output TPS drooped by "
            f"{tps_droop * 100:.1f}%, exceeding max allowed droop of {max_tps_drop_fraction * 100:.1f}%."
        )

    return {
        "gate_evaluated": True,
        "gate_skipped": False,
        "any_failed": any_failed,
        "output_tps_regressed": output_tps_regressed,
        "ttft_ceiling_exceeded": ttft_ceiling_exceeded,
        "gate_reason": " | ".join(reasons) if reasons else "Performance targets achieved within configured budget limits.",
    }


def should_include_verified_context(prompt_text: str) -> bool:
    lowered_prompt = prompt_text.strip().lower()
    return any(marker in lowered_prompt for marker in _VERIFIED_CONTEXT_MARKERS)


def build_verified_eval_prompt(*, prompt_text: str, operating_picture: dict[str, object] | None) -> str:
    if not operating_picture or not should_include_verified_context(prompt_text):
        return prompt_text

    summary = str(operating_picture.get("summary") or "").strip()
    if not summary:
        return prompt_text

    operator_mode = str(operating_picture.get("operator_mode") or "deterministic_server_facts_first")
    return (
        "Verified local context for this run:\n"
        f"- {summary}\n"
        f"- Operator mode: {operator_mode}\n\n"
        "Use the verified local context above as authoritative for current-state questions. "
        "If a requested fact is missing, say it is not verified locally.\n\n"
        f"User prompt:\n{prompt_text}"
    )


def validate_ab_prompt_cases(prompts: object) -> list[dict[str, object]]:
    if not isinstance(prompts, list):
        raise ValueError("A/B prompt pack must be a JSON array of prompt cases.")

    validated_prompts: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(prompts, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Prompt case #{index} must be a JSON object.")

        prompt_id = str(item.get("id") or "").strip()
        prompt_text = str(item.get("prompt") or "").strip()
        if not prompt_id:
            raise ValueError(f"Prompt case #{index} is missing a non-empty id.")
        if prompt_id in seen_ids:
            raise ValueError(f"Prompt pack contains a duplicate id: {prompt_id}")
        if not prompt_text:
            raise ValueError(f"Prompt case '{prompt_id}' is missing a non-empty prompt.")

        assertions = item.get("content_assertions")
        if assertions is not None:
            if not isinstance(assertions, dict):
                raise ValueError(f"Prompt case '{prompt_id}' has a non-object content_assertions block.")
            for key in ("required_contains", "forbidden_contains"):
                values = assertions.get(key, [])
                if not isinstance(values, list) or any(not str(value).strip() for value in values):
                    raise ValueError(f"Prompt case '{prompt_id}' has an invalid {key} list.")
            one_of_groups = assertions.get("required_contains_any", [])
            if not isinstance(one_of_groups, list):
                raise ValueError(f"Prompt case '{prompt_id}' has an invalid required_contains_any list.")
            for group_index, group in enumerate(one_of_groups, start=1):
                if not isinstance(group, list) or not group or any(not str(option).strip() for option in group):
                    raise ValueError(
                        f"Prompt case '{prompt_id}' has an invalid required_contains_any group at position {group_index}."
                    )

        validated_prompts.append(item)
        seen_ids.add(prompt_id)

    return validated_prompts


def evaluate_content_assertions(text: str, assertions: dict[str, object] | None) -> dict[str, object] | None:
    if not isinstance(assertions, dict):
        return None

    lowered_text = text.lower()
    required_contains = [str(item) for item in assertions.get("required_contains", []) if str(item).strip()]
    required_contains_any = [
        [str(option) for option in group if str(option).strip()]
        for group in assertions.get("required_contains_any", [])
        if isinstance(group, list)
    ]
    forbidden_contains = [str(item) for item in assertions.get("forbidden_contains", []) if str(item).strip()]

    missing_required = [item for item in required_contains if item.lower() not in lowered_text]
    missing_required_any = [group for group in required_contains_any if not any(option.lower() in lowered_text for option in group)]
    matched_forbidden = [item for item in forbidden_contains if item.lower() in lowered_text]
    passed = not missing_required and not missing_required_any and not matched_forbidden

    reasons: list[str] = []
    if missing_required:
        reasons.append(f"missing required content: {', '.join(missing_required)}")
    if missing_required_any:
        reasons.append(
            "missing one-of content: "
            + "; ".join(" / ".join(group) for group in missing_required_any)
        )
    if matched_forbidden:
        reasons.append(f"matched forbidden content: {', '.join(matched_forbidden)}")

    return {
        "passed": passed,
        "missing_required": missing_required,
        "missing_required_any": missing_required_any,
        "matched_forbidden": matched_forbidden,
        "reason": " | ".join(reasons) if reasons else "Content assertions passed.",
    }


def build_content_assertion_summary(*, cases: Sequence[dict[str, object]]) -> dict[str, object]:
    baseline_failed_case_ids: list[str] = []
    candidate_failed_case_ids: list[str] = []
    evaluated_case_ids: list[str] = []

    for case in cases:
        case_id = str(case.get("id") or "prompt")
        profile_a_assertions = case.get("profile_a", {}).get("content_assertions") if isinstance(case.get("profile_a"), dict) else None
        profile_b_assertions = case.get("profile_b", {}).get("content_assertions") if isinstance(case.get("profile_b"), dict) else None
        if not isinstance(profile_a_assertions, dict) and not isinstance(profile_b_assertions, dict):
            continue

        evaluated_case_ids.append(case_id)
        if isinstance(profile_a_assertions, dict) and not bool(profile_a_assertions.get("passed")):
            baseline_failed_case_ids.append(case_id)
        if isinstance(profile_b_assertions, dict) and not bool(profile_b_assertions.get("passed")):
            candidate_failed_case_ids.append(case_id)

    return {
        "evaluated_case_count": len(evaluated_case_ids),
        "evaluated_case_ids": evaluated_case_ids,
        "baseline_failed_case_ids": baseline_failed_case_ids,
        "candidate_failed_case_ids": candidate_failed_case_ids,
        "candidate_failed": bool(candidate_failed_case_ids),
    }


def run_ab_comparison(
    *,
    prompts: Sequence[dict[str, str]],
    config: dict[str, Any],
    base_url: str,
    timeout_seconds: int,
    profile_a_alias: str,
    profile_b_alias: str,
    profile_a_base_url: str | None = None,
    profile_b_base_url: str | None = None,
    max_ttft_seconds: float = 0.5,
    max_tps_drop_fraction: float = 0.15,
    dry_run: bool = False,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, object]:
    profile_a = resolve_profile(config, profile_a_alias)
    profile_b = resolve_profile(config, profile_b_alias)
    base_url_a = profile_a_base_url or base_url
    base_url_b = profile_b_base_url or base_url
    operating_picture = get_hal_operating_picture() if {profile_a_alias, profile_b_alias} & {"chat", "chat_second_opinion"} else None

    cases: list[dict[str, object]] = []
    for prompt_case in prompts:
        prompt_id = str(prompt_case.get("id") or "prompt")
        prompt_text = str(prompt_case.get("prompt") or "").strip()
        if not prompt_text:
            continue
        eval_prompt_text = build_verified_eval_prompt(prompt_text=prompt_text, operating_picture=operating_picture)

        if progress_callback:
            progress_callback(f"starting case={prompt_id} profile={profile_a_alias}")

        if dry_run:
            output_a = f"DRY RUN: {profile_a_alias} would answer this prompt."
            output_b = f"DRY RUN: {profile_b_alias} would answer this prompt."
            metrics_a: dict[str, int | float | None] = {
                "load_duration_ns": 0,
                "prompt_eval_duration_ns": 0,
                "eval_duration_ns": 0,
                "total_duration_ns": 0,
                "prompt_eval_count": 0,
                "eval_count": 0,
                "time_to_first_token_estimate_seconds": 0.0,
                "output_tokens_per_second": None,
                "prompt_tokens_per_second": None,
                "end_to_end_tokens_per_second": None,
            }
            metrics_b = dict(metrics_a)
        else:
            result_a = generate_response_result(base_url_a, profile_a, eval_prompt_text, timeout_seconds, seed=profile_a.get("seed"))
            if progress_callback:
                progress_callback(f"completed case={prompt_id} profile={profile_a_alias}")
                progress_callback(f"starting case={prompt_id} profile={profile_b_alias}")
            result_b = generate_response_result(base_url_b, profile_b, eval_prompt_text, timeout_seconds, seed=profile_b.get("seed"))
            output_a = str(result_a["response_text"])
            output_b = str(result_b["response_text"])
            metrics_a = dict(result_a["metrics"])
            metrics_b = dict(result_b["metrics"])

        if progress_callback:
            progress_callback(f"completed case={prompt_id} profile={profile_b_alias}")

        content_assertions = prompt_case.get("content_assertions") if isinstance(prompt_case.get("content_assertions"), dict) else None

        cases.append(
            {
                "id": prompt_id,
                "prompt": prompt_text,
                "profile_a": {
                    "alias": profile_a_alias,
                    "model": profile_a.get("model"),
                    "options": {key: value for key, value in profile_a.items() if key not in {"model", "system_prompt_path"}},
                    "output": output_a,
                    "summary": summarize_output(output_a),
                    "performance": metrics_a,
                    "content_assertions": evaluate_content_assertions(output_a, content_assertions),
                },
                "profile_b": {
                    "alias": profile_b_alias,
                    "model": profile_b.get("model"),
                    "options": {key: value for key, value in profile_b.items() if key not in {"model", "system_prompt_path"}},
                    "output": output_b,
                    "summary": summarize_output(output_b),
                    "performance": metrics_b,
                    "content_assertions": evaluate_content_assertions(output_b, content_assertions),
                },
            }
        )

    profile_summaries = {
        profile_a_alias: build_profile_summary(cases=cases, profile_key="profile_a"),
        profile_b_alias: build_profile_summary(cases=cases, profile_key="profile_b"),
    }
    content_assertion_summary = build_content_assertion_summary(cases=cases)
    regression_flags = build_regression_flags(
        baseline_summary=profile_summaries[profile_a_alias],
        candidate_summary=profile_summaries[profile_b_alias],
        max_ttft_seconds=max_ttft_seconds,
        max_tps_drop_fraction=max_tps_drop_fraction,
        gate_evaluated=not dry_run,
    )
    if content_assertion_summary["candidate_failed"]:
        regression_flags["any_failed"] = True
        regression_flags["content_assertions_failed"] = True
        content_reason = (
            "Candidate content assertions failed for case(s): "
            + ", ".join(content_assertion_summary["candidate_failed_case_ids"])
            + "."
        )
        prior_reason = str(regression_flags.get("gate_reason") or "").strip()
        regression_flags["gate_reason"] = f"{prior_reason} | {content_reason}" if prior_reason else content_reason
    else:
        regression_flags["content_assertions_failed"] = False

    return {
        "profile_a_alias": profile_a_alias,
        "profile_b_alias": profile_b_alias,
        "prompt_count": len(cases),
        "gate_config": {
            "max_ttft_seconds": max_ttft_seconds,
            "max_tps_drop_fraction": max_tps_drop_fraction,
        },
        "profile_summaries": profile_summaries,
        "content_assertion_summary": content_assertion_summary,
        "profile_delta": build_profile_delta(
            baseline_alias=profile_a_alias,
            baseline_summary=profile_summaries[profile_a_alias],
            candidate_alias=profile_b_alias,
            candidate_summary=profile_summaries[profile_b_alias],
        ),
        "regression_flags": regression_flags,
        "cases": cases,
    }