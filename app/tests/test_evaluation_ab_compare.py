from app.evaluation import client as evaluation_client
from app.evaluation.ab_compare import build_content_assertion_summary, build_profile_delta, build_profile_summary, build_regression_flags, build_verified_eval_prompt, count_paragraphs, count_sentences, evaluate_content_assertions, run_ab_comparison, should_include_verified_context, summarize_output


def test_summarize_output_reports_basic_shape():
    summary = summarize_output("First line.\n\nSecond line with more words!")

    assert summary["character_count"] > 0
    assert summary["word_count"] == 7
    assert summary["sentence_count"] == 2
    assert summary["paragraph_count"] == 2
    assert summary["avg_words_per_sentence"] == 3.5


def test_count_sentences_ignores_decimals_and_common_abbreviations():
    text = "Use 0.78 temperature, e.g. for warmer tone. Then keep output tight vs. verbose drift."

    assert count_sentences(text) == 2


def test_count_paragraphs_uses_blank_line_boundaries():
    text = "One paragraph.\n\nTwo paragraph.\n\n\nThree paragraph."

    assert count_paragraphs(text) == 3


def test_run_ab_comparison_uses_requested_profiles(monkeypatch):
    prompts = [{"id": "ops", "prompt": "What matters this morning?"}]
    config = {
        "profiles": {
            "chat": {"model": "mistral-small3.1:24b", "seed": 17},
            "chat_second_opinion": {"model": "qwen3:30b", "seed": 29, "mirostat": 1},
        }
    }

    def fake_generate_response_result(base_url, profile, prompt, timeout_seconds, seed=None):
        return {
            "response_text": f"{profile['model']}::{prompt}::{seed}",
            "metrics": {
                "time_to_first_token_estimate_seconds": 0.42,
                "output_tokens_per_second": 88.5,
                "prompt_tokens_per_second": 321.0,
                "end_to_end_tokens_per_second": 73.25,
            },
            "raw_body": {},
        }

    monkeypatch.setattr("app.evaluation.ab_compare.generate_response_result", fake_generate_response_result)
    monkeypatch.setattr(
        "app.evaluation.ab_compare.get_hal_operating_picture",
        lambda: {"summary": "Verified runtime summary.", "operator_mode": "deterministic_server_facts_first"},
    )

    payload = run_ab_comparison(
        prompts=prompts,
        config=config,
        base_url="http://127.0.0.1:11434",
        timeout_seconds=5,
        profile_a_alias="chat",
        profile_b_alias="chat_second_opinion",
        max_ttft_seconds=0.5,
        max_tps_drop_fraction=0.15,
    )

    assert payload["profile_a_alias"] == "chat"
    assert payload["profile_b_alias"] == "chat_second_opinion"
    assert payload["prompt_count"] == 1
    assert payload["gate_config"] == {"max_ttft_seconds": 0.5, "max_tps_drop_fraction": 0.15}
    assert payload["profile_summaries"]["chat"]["median_ttft_estimate_seconds"] == 0.42
    assert payload["profile_summaries"]["chat_second_opinion"]["median_output_tokens_per_second"] == 88.5
    assert payload["profile_summaries"]["chat_second_opinion"]["average_word_count"] > 4.0
    assert payload["profile_summaries"]["chat_second_opinion"]["median_sentence_count"] >= 1.0
    assert payload["profile_summaries"]["chat_second_opinion"]["median_paragraph_count"] >= 1.0
    assert payload["profile_delta"]["baseline_alias"] == "chat"
    assert payload["profile_delta"]["candidate_alias"] == "chat_second_opinion"
    assert payload["profile_delta"]["candidate_minus_baseline"]["median_ttft_estimate_seconds"] == 0.0
    assert payload["regression_flags"]["gate_evaluated"] is True
    assert payload["regression_flags"]["any_failed"] is False
    case = payload["cases"][0]
    assert case["profile_a"]["output"] == (
        "queen3:14b::Verified local context for this run:\n"
        "- Verified runtime summary.\n"
        "- Operator mode: deterministic_server_facts_first\n\n"
        "Use the verified local context above as authoritative for current-state questions. "
        "If a requested fact is missing, say it is not verified locally.\n\n"
        "User prompt:\nWhat matters this morning?::17"
    )
    assert case["profile_b"]["output"] == (
        "queen3:14b::Verified local context for this run:\n"
        "- Verified runtime summary.\n"
        "- Operator mode: deterministic_server_facts_first\n\n"
        "Use the verified local context above as authoritative for current-state questions. "
        "If a requested fact is missing, say it is not verified locally.\n\n"
        "User prompt:\nWhat matters this morning?::29"
    )
    assert case["profile_b"]["options"]["mirostat"] == 1
    assert case["profile_a"]["performance"]["time_to_first_token_estimate_seconds"] == 0.42
    assert case["profile_b"]["performance"]["output_tokens_per_second"] == 88.5


def test_generate_response_result_applies_prompt_prefix(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run_ollama_generate(*, base_url, model, prompt, system_prompt, options, keep_alive, think, timeout_seconds):
        captured.update(
            {
                "base_url": base_url,
                "model": model,
                "prompt": prompt,
                "system_prompt": system_prompt,
                "options": options,
                "keep_alive": keep_alive,
                "think": think,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {
            "response": "final answer",
            "load_duration": 0,
            "prompt_eval_duration": 0,
            "eval_duration": 0,
            "total_duration": 0,
            "prompt_eval_count": 0,
            "eval_count": 0,
        }

    monkeypatch.setattr(evaluation_client, "run_ollama_generate", fake_run_ollama_generate)

    result = evaluation_client.generate_response_result(
        "http://127.0.0.1:11434",
        {
            "model": "qwen3:30b",
            "seed": 29,
            "prompt_prefix": "/no_think\n",
            "keep_alive": "30m",
            "think": False,
            "strip_thinking_tags": True,
        },
        "What matters this morning?",
        5,
        seed=29,
    )

    assert captured["prompt"] == "/no_think\nWhat matters this morning?"
    assert captured["keep_alive"] == "30m"
    assert captured["think"] is False
    assert result["response_text"] == "final answer"


def test_generate_response_result_retries_after_thinking_only_output(monkeypatch):
    prompts: list[str] = []
    responses = iter(
        [
            {
                "response": "<think>draft internal reasoning only</think>",
                "load_duration": 0,
                "prompt_eval_duration": 0,
                "eval_duration": 0,
                "total_duration": 0,
                "prompt_eval_count": 0,
                "eval_count": 0,
            },
            {
                "response": "SoftDent is the first checkpoint.\n\nQuickBooks is the second checkpoint.",
                "load_duration": 0,
                "prompt_eval_duration": 0,
                "eval_duration": 0,
                "total_duration": 0,
                "prompt_eval_count": 0,
                "eval_count": 0,
            },
        ]
    )

    def fake_run_ollama_generate(*, base_url, model, prompt, system_prompt, options, keep_alive, think, timeout_seconds):
        del base_url, model, system_prompt, options, keep_alive, think, timeout_seconds
        prompts.append(prompt)
        return next(responses)

    monkeypatch.setattr(evaluation_client, "run_ollama_generate", fake_run_ollama_generate)

    result = evaluation_client.generate_response_result(
        "http://127.0.0.1:11434",
        {
            "model": "qwen3:30b",
            "seed": 29,
            "prompt_prefix": "/no_think\n",
            "keep_alive": "30m",
            "strip_thinking_tags": True,
        },
        "Talk to me like a steady operator.",
        5,
        seed=29,
    )

    assert prompts == [
        "/no_think\nTalk to me like a steady operator.",
        "/no_think\nTalk to me like a steady operator.\n\nIMPORTANT: Return only the final answer. Do not include <think> tags, hidden reasoning, or scratchpad. If you started internal reasoning, suppress it and answer directly in the requested format.",
    ]
    assert result["response_text"] == "SoftDent is the first checkpoint.\n\nQuickBooks is the second checkpoint."
    assert result["metrics"]["retry_attempted"] is True
    assert result["metrics"]["initial_attempt_metrics"]["eval_count"] == 0


def test_run_ollama_generate_sends_think_flag(monkeypatch):
    captured: dict[str, object] = {}

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "response": "final answer",
                "load_duration": 0,
                "prompt_eval_duration": 0,
                "eval_duration": 0,
                "total_duration": 0,
                "prompt_eval_count": 0,
                "eval_count": 0,
            }

    def fake_post(url, *, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr(evaluation_client.requests, "post", fake_post)

    body = evaluation_client.run_ollama_generate(
        base_url="http://127.0.0.1:11435",
        model="qwen3:30b",
        prompt="What denied patient claims need follow-up?",
        system_prompt=None,
        options={"num_predict": 192},
        keep_alive="30m",
        think=False,
        timeout_seconds=30,
    )

    assert body["response"] == "final answer"
    assert captured["url"] == "http://127.0.0.1:11435/api/generate"
    assert captured["json"]["think"] is False


def test_generate_response_result_uses_litellm_proxy_alias_when_proxy_base_url_matches(monkeypatch):
    monkeypatch.setenv("LITELLM_PROXY_BASE_URL", "http://127.0.0.1:4000")
    monkeypatch.setenv("LITELLM_MASTER_KEY", "sk-local-test")

    captured: dict[str, object] = {}

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "proxy answer",
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 8,
                },
            }

    def fake_post(url, json, timeout, headers=None):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        captured["headers"] = headers
        return _FakeResponse()

    monkeypatch.setattr(evaluation_client.requests, "post", fake_post)

    result = evaluation_client.generate_response_result(
        "http://127.0.0.1:4000",
        {
            "model": "qwen3:30b",
            "litellm_model": "hal-second-opinion",
            "seed": 29,
            "system_prompt_path": None,
        },
        "Review the operator note.",
        30,
        seed=29,
    )

    assert captured["url"] == "http://127.0.0.1:4000/chat/completions"
    assert captured["json"] == {
        "model": "hal-second-opinion",
        "messages": [
            {"role": "user", "content": "Review the operator note."},
        ],
        "stream": False,
        "temperature": 0,
        "top_p": 1,
        "seed": 29,
    }
    assert captured["headers"] == {"Authorization": "Bearer sk-local-test"}
    assert result["response_text"] == "proxy answer"
    assert result["metrics"]["prompt_eval_count"] == 12
    assert result["metrics"]["eval_count"] == 8


def test_build_verified_eval_prompt_wraps_authoritative_context():
    prompt = build_verified_eval_prompt(
        prompt_text="Give me the current HAL operating picture.",
        operating_picture={
            "summary": "Ollama is reachable. SoftDent aggregates are live. QuickBooks revenue lane health is healthy.",
            "operator_mode": "deterministic_server_facts_first",
        },
    )

    assert "Verified local context for this run:" in prompt
    assert "Ollama is reachable. SoftDent aggregates are live." in prompt
    assert "Operator mode: deterministic_server_facts_first" in prompt
    assert prompt.endswith("User prompt:\nGive me the current HAL operating picture.")


def test_should_include_verified_context_only_for_current_state_prompts():
    assert should_include_verified_context("Give me the current HAL operating picture.") is True
    assert should_include_verified_context("Talk to me like a steady operator. What matters most this morning?") is True
    assert should_include_verified_context("Can you post this QuickBooks adjustment for me right now?") is False
    assert should_include_verified_context("SoftDent collections are trailing production. What should I look at first?") is False


def test_build_verified_eval_prompt_skips_generic_workflow_prompts_even_with_context():
    prompt = build_verified_eval_prompt(
        prompt_text="SoftDent collections are trailing production. What should I look at first?",
        operating_picture={
            "summary": "Ollama is reachable. SoftDent aggregates are live. QuickBooks revenue lane health is healthy.",
            "operator_mode": "deterministic_server_facts_first",
        },
    )

    assert prompt == "SoftDent collections are trailing production. What should I look at first?"


def test_evaluate_content_assertions_reports_missing_and_forbidden_content():
    result = evaluate_content_assertions(
        "QuickBooks is read-only here, but traffic is heavy.",
        {
            "required_contains": ["QuickBooks", "cannot"],
            "required_contains_any": [["follow up", "resubmit"]],
            "forbidden_contains": ["traffic"],
        },
    )

    assert result == {
        "passed": False,
        "missing_required": ["cannot"],
        "missing_required_any": [["follow up", "resubmit"]],
        "matched_forbidden": ["traffic"],
        "reason": "missing required content: cannot | missing one-of content: follow up / resubmit | matched forbidden content: traffic",
    }


def test_build_content_assertion_summary_tracks_candidate_failures():
    summary = build_content_assertion_summary(
        cases=[
            {
                "id": "ops-brief",
                "profile_a": {"content_assertions": {"passed": True}},
                "profile_b": {"content_assertions": {"passed": False}},
            },
            {
                "id": "softdent-risk",
                "profile_a": {"content_assertions": {"passed": False}},
                "profile_b": {"content_assertions": {"passed": True}},
            },
        ]
    )

    assert summary == {
        "evaluated_case_count": 2,
        "evaluated_case_ids": ["ops-brief", "softdent-risk"],
        "baseline_failed_case_ids": ["softdent-risk"],
        "candidate_failed_case_ids": ["ops-brief"],
        "candidate_failed": True,
    }


def test_run_ab_comparison_marks_candidate_content_assertion_failures(monkeypatch):
    prompts = [
        {
            "id": "ops",
            "prompt": "What matters this morning?",
            "content_assertions": {
                "required_contains": ["Ollama"],
                "forbidden_contains": ["weather"],
            },
        }
    ]
    config = {
        "profiles": {
            "chat": {"model": "mistral-small3.1:24b", "seed": 17},
            "chat_second_opinion": {"model": "qwen3:30b", "seed": 29},
        }
    }

    def fake_generate_response_result(base_url, profile, prompt, timeout_seconds, seed=None):
        if seed == 17:
            response_text = "Ollama is reachable and SoftDent is live."
        else:
            response_text = "The weather looks fine today."
        return {
            "response_text": response_text,
            "metrics": {
                "time_to_first_token_estimate_seconds": 0.42,
                "output_tokens_per_second": 88.5,
                "prompt_tokens_per_second": 321.0,
                "end_to_end_tokens_per_second": 73.25,
            },
            "raw_body": {},
        }

    monkeypatch.setattr("app.evaluation.ab_compare.generate_response_result", fake_generate_response_result)
    monkeypatch.setattr(
        "app.evaluation.ab_compare.get_hal_operating_picture",
        lambda: {"summary": "Verified runtime summary.", "operator_mode": "deterministic_server_facts_first"},
    )

    payload = run_ab_comparison(
        prompts=prompts,
        config=config,
        base_url="http://127.0.0.1:11434",
        timeout_seconds=5,
        profile_a_alias="chat",
        profile_b_alias="chat_second_opinion",
        max_ttft_seconds=5,
        max_tps_drop_fraction=0.5,
    )

    assert payload["content_assertion_summary"] == {
        "evaluated_case_count": 1,
        "evaluated_case_ids": ["ops"],
        "baseline_failed_case_ids": [],
        "candidate_failed_case_ids": ["ops"],
        "candidate_failed": True,
    }
    assert payload["cases"][0]["profile_b"]["content_assertions"] == {
        "passed": False,
        "missing_required": ["Ollama"],
        "missing_required_any": [],
        "matched_forbidden": ["weather"],
        "reason": "missing required content: Ollama | matched forbidden content: weather",
    }
    assert payload["regression_flags"]["content_assertions_failed"] is True
    assert payload["regression_flags"]["any_failed"] is True
    assert "Candidate content assertions failed for case(s): ops." in payload["regression_flags"]["gate_reason"]


def test_build_profile_summary_aggregates_medians_and_averages():
    cases = [
        {
            "profile_a": {
                "summary": {"word_count": 10, "character_count": 50, "sentence_count": 2, "paragraph_count": 1},
                "performance": {
                    "time_to_first_token_estimate_seconds": 0.4,
                    "output_tokens_per_second": 90.0,
                    "end_to_end_tokens_per_second": 70.0,
                },
            }
        },
        {
            "profile_a": {
                "summary": {"word_count": 20, "character_count": 100, "sentence_count": 4, "paragraph_count": 3},
                "performance": {
                    "time_to_first_token_estimate_seconds": 0.6,
                    "output_tokens_per_second": 110.0,
                    "end_to_end_tokens_per_second": 80.0,
                },
            }
        },
    ]

    summary = build_profile_summary(cases=cases, profile_key="profile_a")

    assert summary == {
        "case_count": 2,
        "median_ttft_estimate_seconds": 0.5,
        "median_output_tokens_per_second": 100.0,
        "median_end_to_end_tokens_per_second": 75.0,
        "average_word_count": 15.0,
        "average_character_count": 75.0,
        "median_sentence_count": 3.0,
        "median_paragraph_count": 2.0,
    }


def test_build_profile_delta_compares_candidate_against_baseline():
    delta = build_profile_delta(
        baseline_alias="chat",
        baseline_summary={
            "median_ttft_estimate_seconds": 0.4,
            "median_output_tokens_per_second": 90.0,
            "median_end_to_end_tokens_per_second": 70.0,
            "average_word_count": 10.0,
            "average_character_count": 50.0,
            "median_sentence_count": 2.0,
            "median_paragraph_count": 1.0,
        },
        candidate_alias="chat_second_opinion",
        candidate_summary={
            "median_ttft_estimate_seconds": 0.55,
            "median_output_tokens_per_second": 82.5,
            "median_end_to_end_tokens_per_second": 65.0,
            "average_word_count": 14.0,
            "average_character_count": 61.0,
            "median_sentence_count": 5.0,
            "median_paragraph_count": 3.0,
        },
    )

    assert delta == {
        "baseline_alias": "chat",
        "candidate_alias": "chat_second_opinion",
        "candidate_minus_baseline": {
            "median_ttft_estimate_seconds": 0.15,
            "median_output_tokens_per_second": -7.5,
            "median_end_to_end_tokens_per_second": -5.0,
            "average_word_count": 4.0,
            "average_character_count": 11.0,
            "median_sentence_count": 3.0,
            "median_paragraph_count": 2.0,
        },
    }


def test_build_regression_flags_detects_tps_drop_and_ttft_ceiling():
    flags = build_regression_flags(
        baseline_summary={"median_output_tokens_per_second": 100.0},
        candidate_summary={
            "median_output_tokens_per_second": 80.0,
            "median_ttft_estimate_seconds": 0.61,
        },
        max_ttft_seconds=0.5,
        max_tps_drop_fraction=0.15,
        gate_evaluated=True,
    )

    assert flags == {
        "gate_evaluated": True,
        "gate_skipped": False,
        "any_failed": True,
        "output_tps_regressed": True,
        "ttft_ceiling_exceeded": True,
        "gate_reason": "Candidate median TTFT (0.610s) exceeded absolute ceiling of 0.500s. | Candidate median output TPS drooped by 20.0%, exceeding max allowed droop of 15.0%.",
    }


def test_build_regression_flags_skips_gate_for_dry_run():
    flags = build_regression_flags(
        baseline_summary={"median_output_tokens_per_second": 100.0},
        candidate_summary={"median_ttft_estimate_seconds": 0.61},
        max_ttft_seconds=0.5,
        max_tps_drop_fraction=0.15,
        gate_evaluated=False,
    )

    assert flags == {
        "gate_evaluated": False,
        "gate_skipped": True,
        "any_failed": False,
        "output_tps_regressed": False,
        "ttft_ceiling_exceeded": False,
        "gate_reason": "Gate evaluation skipped because the run was executed in dry-run mode.",
    }


def test_build_regression_flags_reports_passing_reason():
    flags = build_regression_flags(
        baseline_summary={"median_output_tokens_per_second": 100.0},
        candidate_summary={
            "median_output_tokens_per_second": 95.0,
            "median_ttft_estimate_seconds": 0.41,
        },
        max_ttft_seconds=0.5,
        max_tps_drop_fraction=0.15,
        gate_evaluated=True,
    )

    assert flags["any_failed"] is False
    assert flags["gate_reason"] == "Performance targets achieved within configured budget limits."


def test_build_regression_flags_reports_tps_regression_reason():
    flags = build_regression_flags(
        baseline_summary={"median_output_tokens_per_second": 100.0},
        candidate_summary={
            "median_output_tokens_per_second": 80.0,
            "median_ttft_estimate_seconds": 0.41,
        },
        max_ttft_seconds=0.5,
        max_tps_drop_fraction=0.15,
        gate_evaluated=True,
    )

    assert flags["output_tps_regressed"] is True
    assert "Candidate median output TPS drooped by" in flags["gate_reason"]
    assert "exceeding max allowed droop" in flags["gate_reason"]