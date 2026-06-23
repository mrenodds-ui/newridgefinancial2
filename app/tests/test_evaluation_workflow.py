from app.evaluation.client import (
    ResponseValidationError,
    build_retry_prompt,
    build_options,
    extract_ollama_generate_metrics,
    generate_response_with_validation,
    run_python_validation,
    strip_thinking_tags,
    run_structured_output_workflow,
    validate_json_object_response,
)


def test_build_options_includes_extended_sampling_controls():
    options = build_options(
        {
            "temperature": 0.78,
            "top_p": 0.9,
            "repeat_penalty": 1.08,
            "repeat_last_n": 64,
            "mirostat": 1,
            "mirostat_tau": 5,
            "mirostat_eta": 0.1,
            "seed": 17,
        }
    )

    assert options == {
        "temperature": 0.78,
        "top_p": 0.9,
        "repeat_penalty": 1.08,
        "repeat_last_n": 64,
        "mirostat": 1,
        "mirostat_tau": 5,
        "mirostat_eta": 0.1,
        "seed": 17,
    }


def test_strip_thinking_tags_removes_private_reasoning():
    response_text = "<think>private chain of thought</think>Final answer."

    assert strip_thinking_tags(response_text) == "Final answer."


def test_extract_ollama_generate_metrics_reports_ttft_and_tps():
    metrics = extract_ollama_generate_metrics(
        {
            "load_duration": 100_000_000,
            "prompt_eval_duration": 200_000_000,
            "eval_duration": 500_000_000,
            "total_duration": 900_000_000,
            "prompt_eval_count": 100,
            "eval_count": 50,
        }
    )

    assert metrics["load_duration_ns"] == 100_000_000
    assert metrics["prompt_eval_duration_ns"] == 200_000_000
    assert metrics["eval_duration_ns"] == 500_000_000
    assert metrics["prompt_eval_count"] == 100
    assert metrics["eval_count"] == 50
    assert metrics["time_to_first_token_estimate_seconds"] == 0.31
    assert metrics["output_tokens_per_second"] == 100.0
    assert metrics["prompt_tokens_per_second"] == 500.0
    assert metrics["end_to_end_tokens_per_second"] == 166.67


def test_validate_json_object_response_accepts_fenced_json():
    payload = validate_json_object_response(
        """```json
        {"invoice_id": "INV-7", "amount": 12.5}
        ```""",
        required_keys=["invoice_id", "amount"],
    )
    assert payload == {"invoice_id": "INV-7", "amount": 12.5}


def test_generate_response_with_validation_retries_after_validation_error(monkeypatch):
    prompts: list[str] = []
    responses = iter(["not json", '{"status": "ok"}'])

    def fake_generate_response(*, base_url, profile, prompt, timeout_seconds, seed=None):
        prompts.append(prompt)
        return next(responses)

    monkeypatch.setattr("app.evaluation.client.generate_response", fake_generate_response)

    response_text, payload = generate_response_with_validation(
        base_url="http://127.0.0.1:11434",
        profile={"model": "fake"},
        prompt="Return JSON only.",
        timeout_seconds=5,
        validator=lambda text: validate_json_object_response(text, required_keys=["status"]),
        max_attempts=2,
    )

    assert response_text == '{"status": "ok"}'
    assert payload == {"status": "ok"}
    assert prompts[0] == "Return JSON only."
    assert "Your previous output failed validation" in prompts[1]
    assert "Previous output:\nnot json" in prompts[1]


def test_run_python_validation_raises_on_failed_dict_result():
    try:
        run_python_validation({"amount": -5}, validator=lambda payload: {"passed": False, "error": "amount must be non-negative"})
    except ResponseValidationError as exc:
        assert str(exc) == "amount must be non-negative"
    else:
        raise AssertionError("Expected ResponseValidationError")


def test_run_structured_output_workflow_runs_parse_validate_and_summarize(monkeypatch):
    prompts: list[str] = []
    responses = iter([
        '{"invoice_id": "INV-1", "amount": 125.0}',
        "Invoice INV-1 balanced successfully.",
    ])

    def fake_generate_response(*, base_url, profile, prompt, timeout_seconds, seed=None):
        prompts.append(prompt)
        return next(responses)

    monkeypatch.setattr("app.evaluation.client.generate_response", fake_generate_response)

    result = run_structured_output_workflow(
        base_url="http://127.0.0.1:11434",
        parser_profile={"model": "qwen"},
        narrator_profile={"model": "mistral"},
        source_text="Invoice INV-1 for $125.00",
        parse_instructions="Extract invoice_id and amount.",
        summary_instructions="Summarize the validated invoice in one sentence.",
        timeout_seconds=5,
        required_keys=["invoice_id", "amount"],
        validator=lambda payload: {"passed": payload["amount"] >= 0, "details": "Ledger amount is non-negative."},
    )

    assert result["parsed_payload"] == {"invoice_id": "INV-1", "amount": 125.0}
    assert result["validation_result"] == {"passed": True, "details": "Ledger amount is non-negative."}
    assert result["summary_text"] == "Invoice INV-1 balanced successfully."
    assert "Source text:\nInvoice INV-1 for $125.00" in prompts[0]
    assert '"invoice_id": "INV-1"' in prompts[1]
    assert '"passed": true' in prompts[1]


def test_build_retry_prompt_preserves_original_instructions():
    prompt = build_retry_prompt(
        original_prompt="Return JSON only.",
        previous_output="Here is your answer",
        error_message="Expected valid JSON output from the model.",
    )
    assert "Original instructions:\nReturn JSON only." in prompt
    assert "Validation error:\nExpected valid JSON output from the model." in prompt