from app.evaluation.engine import (
    INSUFFICIENT_CONTEXT_TOKEN,
    build_reference_facts_prompt,
    build_retrieval_prompt,
    compute_context_precision,
    evaluate_exact_case,
    evaluate_format_case,
    evaluate_judge_output,
    evaluate_retrieval_case,
)


def test_compute_context_precision_returns_ratio():
    precision = compute_context_precision(["a", "b", "c"], ["b", "c"])
    assert precision == 0.6667


def test_evaluate_format_case_rejects_non_json_fluff():
    case = {"id": "json-case", "required_keys": ["action"]}
    result = evaluate_format_case(case, "Sure, here you go: {\"action\": \"emit\"}")
    assert result["passed"] is False
    assert "invalid_json" in result["failure_reason"]


def test_evaluate_exact_case_enforces_exact_match():
    case = {"id": "amount-case", "expected_equals": "$1,250.45"}
    result = evaluate_exact_case(case, "$1,250.45")
    assert result["passed"] is True


def test_build_retrieval_prompt_includes_fail_closed_instruction():
    prompt = build_retrieval_prompt(
        {
            "prompt": "What is allowed?",
            "context_chunks": [{"id": "ctx-1", "text": "Read-only summaries only."}],
        }
    )
    assert INSUFFICIENT_CONTEXT_TOKEN in prompt
    assert "[ctx-1] Read-only summaries only." in prompt
    assert "If the context directly answers the question" in prompt
    assert "If the context includes both a current restriction and a future or alternate path" in prompt


def test_build_reference_facts_prompt_includes_reference_facts():
    prompt = build_reference_facts_prompt(
        {
            "prompt": "Summarize the privacy boundary.",
            "reference_facts": [
                "Use sanitized summaries.",
                "Fail closed when context is missing.",
            ],
        }
    )
    assert INSUFFICIENT_CONTEXT_TOKEN in prompt
    assert "- Use sanitized summaries." in prompt
    assert "- Fail closed when context is missing." in prompt
    assert "Cover all supplied facts without omission" in prompt


def test_evaluate_judge_output_respects_judge_pass_flag():
    case = {"id": "judge-case", "minimum_average_score": 4.2}
    result = evaluate_judge_output(
        case,
        """```json
{
  \"scores\": {\"grounding\": 4, \"coverage\": 4, \"format\": 5, \"tone\": 5},
  \"average_score\": 4.5,
  \"pass\": false,
  \"rationale\": \"Still missing a required fact.\"
}
```""",
    )
    assert result["passed"] is False
    assert result["failure_reason"] == "judge_marked_failed"


def test_evaluate_retrieval_case_requires_fail_closed_when_context_missing():
    case = {
        "id": "missing",
        "expected_mode": "insufficient_context",
        "retrieved_context_ids": ["ctx-1"],
        "relevant_context_ids": ["ctx-1"],
    }
    result = evaluate_retrieval_case(case, INSUFFICIENT_CONTEXT_TOKEN)
    assert result["passed"] is True


def test_evaluate_retrieval_case_accepts_required_phrase_group_match():
    case = {
        "id": "group-match",
        "retrieved_context_ids": ["ctx-1"],
        "relevant_context_ids": ["ctx-1"],
        "required_phrase_groups": [["separate local posting worker", "direct tool surface"]],
    }
    result = evaluate_retrieval_case(case, "Posting must not be part of HAL's direct tool surface.")
    assert result["passed"] is True


def test_evaluate_judge_output_accepts_fenced_json():
    case = {"id": "judge-case", "minimum_average_score": 4.2}
    result = evaluate_judge_output(
        case,
        """```json
{
  \"scores\": {\"grounding\": 5, \"coverage\": 4, \"format\": 5, \"tone\": 4},
  \"average_score\": 4.5,
  \"pass\": true,
  \"rationale\": \"Grounded and complete.\"
}
```""",
    )
    assert result["passed"] is True
    assert result["average_score"] == 4.5