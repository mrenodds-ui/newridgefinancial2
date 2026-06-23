from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .client import generate_response, load_text_file, resolve_profile

INSUFFICIENT_CONTEXT_TOKEN = "INSUFFICIENT_CONTEXT"


def compute_context_precision(retrieved_context_ids: list[str], relevant_context_ids: list[str]) -> float:
    if not retrieved_context_ids:
        return 0.0
    relevant = set(relevant_context_ids)
    matches = sum(1 for item in retrieved_context_ids if item in relevant)
    return round(matches / len(retrieved_context_ids), 4)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def split_text_into_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(0, end - overlap)
    return chunks


def strict_json_loads(text: str) -> dict[str, Any]:
    payload = json.loads(text.strip())
    if not isinstance(payload, dict):
        raise ValueError("Expected a top-level JSON object.")
    return payload


def extract_json_object(text: str) -> str:
    stripped = text.strip()
    fenced_match = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", stripped, flags=re.DOTALL)
    if fenced_match:
        return fenced_match.group(1).strip()
    return stripped


def try_parse_json_object(text: str) -> dict[str, Any] | None:
    try:
        return strict_json_loads(extract_json_object(text))
    except (json.JSONDecodeError, ValueError):
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return strict_json_loads(match.group(0))
        except (json.JSONDecodeError, ValueError):
            return None


def assert_required_keys(payload: dict[str, Any], required_keys: list[str]) -> list[str]:
    return [key for key in required_keys if key not in payload]


def build_retrieval_prompt(case: dict[str, Any]) -> str:
    context_chunks = []
    for item in case.get("context_chunks", []):
        context_chunks.append(f"[{item['id']}] {item['text']}")
    rendered_context = "\n\n".join(context_chunks)
    question = case["prompt"]
    return (
        "Answer only from the provided context. "
        "If the context directly answers the question, answer concisely and use the same safety terms from the context. "
        "Include every context-backed constraint needed for a safe answer. "
        "If the context includes both a current restriction and a future or alternate path, mention both. "
        f"If the answer is not fully supported by the context, reply with exactly {INSUFFICIENT_CONTEXT_TOKEN}.\n\n"
        f"Context:\n{rendered_context}\n\n"
        f"Question: {question}\n"
    )


def build_reference_facts_prompt(case: dict[str, Any]) -> str:
    reference_facts = "\n".join(f"- {fact}" for fact in case.get("reference_facts", []))
    return (
        "Answer only from the supplied reference facts. "
        "Do not add claims that are not stated in those facts. "
        "Cover all supplied facts without omission and match the requested format as closely as possible. "
        f"If the facts do not fully support an answer, reply with exactly {INSUFFICIENT_CONTEXT_TOKEN}.\n\n"
        f"Reference facts:\n{reference_facts}\n\n"
        f"Question: {case['prompt']}\n"
    )


def build_judge_prompt(case: dict[str, Any], rubric_text: str, answer_text: str) -> str:
    reference_facts = "\n".join(f"- {fact}" for fact in case.get("reference_facts", []))
    return (
        "You are an LLM regression judge. Grade the candidate answer against the rubric and reference facts. "
        "Return JSON only with keys: scores, average_score, pass, rationale.\n\n"
        f"Rubric:\n{rubric_text}\n\n"
        f"Question:\n{case['prompt']}\n\n"
        f"Reference facts:\n{reference_facts}\n\n"
        f"Candidate answer:\n{answer_text}\n"
    )


def evaluate_assertions(output_text: str, assertions: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for assertion in assertions:
        assertion_type = assertion["type"]
        if assertion_type == "json_parse":
            if try_parse_json_object(output_text) is None:
                failures.append("expected valid JSON output")
        elif assertion_type == "json_keys":
            parsed = try_parse_json_object(output_text)
            if parsed is None:
                failures.append("expected JSON before key validation")
            else:
                missing = [key for key in assertion["keys"] if key not in parsed]
                if missing:
                    failures.append(f"missing JSON keys: {', '.join(missing)}")
        elif assertion_type == "contains":
            if assertion["value"] not in output_text:
                failures.append(f"missing required substring: {assertion['value']}")
        elif assertion_type == "not_contains":
            if assertion["value"] in output_text:
                failures.append(f"found forbidden substring: {assertion['value']}")
        elif assertion_type == "exact_match":
            if normalize_text(output_text) != normalize_text(assertion["value"]):
                failures.append(f"expected exact match: {assertion['value']}")
        elif assertion_type == "regex":
            if re.search(assertion["pattern"], output_text) is None:
                failures.append(f"regex did not match: {assertion['pattern']}")
        else:
            failures.append(f"unsupported assertion type: {assertion_type}")
    return failures


def evaluate_format_case(case: dict[str, Any], response_text: str) -> dict[str, Any]:
    details: dict[str, Any] = {
        "case_id": case["id"],
        "type": "format_assertion",
        "passed": False,
        "response": response_text,
    }
    try:
        payload = strict_json_loads(response_text)
    except Exception as exc:
        details["failure_reason"] = f"invalid_json: {exc}"
        return details

    missing_keys = assert_required_keys(payload, case.get("required_keys", []))
    if missing_keys:
        details["failure_reason"] = f"missing_keys: {', '.join(missing_keys)}"
        details["parsed"] = payload
        return details

    details["passed"] = True
    details["parsed"] = payload
    return details


def evaluate_exact_case(case: dict[str, Any], response_text: str) -> dict[str, Any]:
    normalized = response_text.strip()
    details: dict[str, Any] = {
        "case_id": case["id"],
        "type": "exact_value_assertion",
        "passed": True,
        "response": normalized,
    }

    expected_equals = case.get("expected_equals")
    if expected_equals is not None and normalized != expected_equals:
        details["passed"] = False
        details["failure_reason"] = f"expected_exact_match: {expected_equals}"

    for expected_fragment in case.get("expected_contains", []):
        if expected_fragment not in normalized:
            details["passed"] = False
            details.setdefault("failure_reason", "missing_expected_fragment")
            details.setdefault("missing_fragments", []).append(expected_fragment)

    for forbidden_fragment in case.get("forbidden_contains", []):
        if forbidden_fragment in normalized:
            details["passed"] = False
            details.setdefault("failure_reason", "contained_forbidden_fragment")
            details.setdefault("forbidden_fragments", []).append(forbidden_fragment)

    return details


def evaluate_retrieval_case(case: dict[str, Any], response_text: str) -> dict[str, Any]:
    normalized = response_text.strip()
    retrieved_context_ids = case.get("retrieved_context_ids", [])
    relevant_context_ids = case.get("relevant_context_ids", [])
    context_precision = compute_context_precision(retrieved_context_ids, relevant_context_ids)
    threshold = case.get("minimum_context_precision", 0.7)
    expected_mode = case.get("expected_mode", "answer")

    details: dict[str, Any] = {
        "case_id": case["id"],
        "type": "retrieval_assertion",
        "passed": True,
        "response": normalized,
        "context_precision": context_precision,
        "minimum_context_precision": threshold,
    }

    if retrieved_context_ids:
        details["passed"] = context_precision >= threshold
        if not details["passed"]:
            details["failure_reason"] = "context_precision_below_threshold"

    if expected_mode == "insufficient_context":
        if normalized != INSUFFICIENT_CONTEXT_TOKEN:
            details["passed"] = False
            details["failure_reason"] = "model_should_have_failed_closed"
        return details

    if normalized == INSUFFICIENT_CONTEXT_TOKEN:
        details["passed"] = False
        details["failure_reason"] = "model_failed_closed_with_supported_context"
        return details

    for expected_fragment in case.get("required_phrases", []):
        if expected_fragment not in normalized:
            details["passed"] = False
            details.setdefault("failure_reason", "missing_required_phrase")
            details.setdefault("missing_required_phrases", []).append(expected_fragment)

    for phrase_group in case.get("required_phrase_groups", []):
        if not any(fragment in normalized for fragment in phrase_group):
            details["passed"] = False
            details.setdefault("failure_reason", "missing_required_phrase_group")
            details.setdefault("missing_required_phrase_groups", []).append(phrase_group)

    for forbidden_fragment in case.get("forbidden_phrases", []):
        if forbidden_fragment in normalized:
            details["passed"] = False
            details.setdefault("failure_reason", "response_contains_forbidden_phrase")
            details.setdefault("forbidden_phrases_found", []).append(forbidden_fragment)

    return details


def evaluate_judge_output(case: dict[str, Any], judge_output_text: str) -> dict[str, Any]:
    details: dict[str, Any] = {
        "case_id": case["id"],
        "type": "judge_assertion",
        "passed": False,
        "judge_output": judge_output_text,
    }
    try:
        parsed = strict_json_loads(extract_json_object(judge_output_text))
    except Exception as exc:
        details["failure_reason"] = f"invalid_judge_json: {exc}"
        return details

    average_score = float(parsed.get("average_score", 0.0))
    threshold = float(case.get("minimum_average_score", 4.5))
    judge_pass = parsed.get("pass")
    details["parsed"] = parsed
    details["average_score"] = average_score
    details["minimum_average_score"] = threshold
    if isinstance(judge_pass, bool):
        details["judge_pass"] = judge_pass

    details["passed"] = average_score >= threshold and judge_pass is not False
    if average_score < threshold:
        details["failure_reason"] = "judge_score_below_threshold"
    elif judge_pass is False:
        details["failure_reason"] = "judge_marked_failed"
    return details


def run_assertion_cases(dataset: dict[str, Any], config: dict[str, Any], base_url: str, timeout_seconds: int, dry_run: bool) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    for case in dataset.get("format_assertions", []):
        profile = resolve_profile(config, case["model_alias"])
        if dry_run:
            results.append({"case_id": case["id"], "type": "format_assertion", "passed": True, "skipped": True})
            continue
        response_text = generate_response(base_url, profile, case["prompt"], timeout_seconds)
        results.append(evaluate_format_case(case, response_text))

    for case in dataset.get("exact_value_assertions", []):
        profile = resolve_profile(config, case["model_alias"])
        if dry_run:
            results.append({"case_id": case["id"], "type": "exact_value_assertion", "passed": True, "skipped": True})
            continue
        response_text = generate_response(base_url, profile, case["prompt"], timeout_seconds)
        results.append(evaluate_exact_case(case, response_text))

    for case in dataset.get("retrieval_assertions", []):
        profile = resolve_profile(config, case["model_alias"])
        if dry_run:
            results.append({"case_id": case["id"], "type": "retrieval_assertion", "passed": True, "skipped": True})
            continue
        prompt = build_retrieval_prompt(case)
        response_text = generate_response(base_url, profile, prompt, timeout_seconds)
        results.append(evaluate_retrieval_case(case, response_text))

    return results


def run_judge_cases(dataset: dict[str, Any], config: dict[str, Any], base_url: str, timeout_seconds: int, dry_run: bool) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    judge_alias = config.get("judge_profile_alias")
    rubric_path = config.get("judge_rubric_path")
    if not judge_alias or not rubric_path:
        return results

    judge_profile = resolve_profile(config, judge_alias)
    rubric_text = load_text_file(Path(rubric_path)) or ""

    for case in dataset.get("judge_assertions", []):
        candidate_profile = resolve_profile(config, case["model_alias"])
        seeds = case.get("candidate_seeds", [candidate_profile.get("seed")])
        case_scores = []
        case_details = []

        if dry_run:
            results.append({"case_id": case["id"], "type": "judge_assertion", "passed": True, "skipped": True})
            continue

        for seed in seeds:
            candidate_prompt = build_reference_facts_prompt(case)
            answer_text = generate_response(base_url, candidate_profile, candidate_prompt, timeout_seconds, seed=seed)
            judge_prompt = build_judge_prompt(case, rubric_text, answer_text)
            judge_output_text = generate_response(base_url, judge_profile, judge_prompt, timeout_seconds, seed=judge_profile.get("seed"))
            evaluation = evaluate_judge_output(case, judge_output_text)
            evaluation["candidate_seed"] = seed
            evaluation["candidate_answer"] = answer_text
            case_details.append(evaluation)
            if evaluation.get("average_score") is not None:
                case_scores.append(float(evaluation["average_score"]))

        aggregate_average = round(sum(case_scores) / len(case_scores), 4) if case_scores else 0.0
        minimum_average_score = float(case.get("minimum_average_score", 4.5))
        results.append(
            {
                "case_id": case["id"],
                "type": "judge_assertion",
                "passed": bool(case_scores) and aggregate_average >= minimum_average_score and all(item["passed"] for item in case_details),
                "average_score": aggregate_average,
                "minimum_average_score": minimum_average_score,
                "runs": case_details,
            }
        )

    return results
