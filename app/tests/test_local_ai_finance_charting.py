import json
from pathlib import Path

from local_ai_finance import main as local_ai_finance


def test_validate_chart_payload_accepts_expected_shape() -> None:
    payload = {
        "chart_config": {
            "chart_type": "bar",
            "title": "June Expense Breakdown",
            "x_axis_label": "Category",
            "y_axis_label": "Amount",
        },
        "chart_data": [
            {"label": "Software", "value": 540.0},
            {"label": "Rent", "value": 1200.0},
        ],
    }

    validated = local_ai_finance.validate_chart_payload(payload)

    assert validated == payload


def test_render_chart_from_request_writes_png(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(local_ai_finance, "WORKSPACE_DIR", tmp_path)
    log_path = tmp_path / "ai_activity.log"
    monkeypatch.setattr(local_ai_finance, "LOG_FILE", log_path)
    local_ai_finance.ensure_workspace()
    request_path = tmp_path / "chart-request.json"
    request_path.write_text(
        json.dumps(
            {
                "chart_config": {
                    "chart_type": "bar",
                    "title": "June Expense Breakdown",
                    "x_axis_label": "Category",
                    "y_axis_label": "Amount",
                },
                "chart_data": [
                    {"label": "Software", "value": 540.0},
                    {"label": "Rent", "value": 1200.0},
                    {"label": "Supplies", "value": 85.0},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(local_ai_finance, "review_step", lambda plan_text: None)

    output_path = local_ai_finance.render_chart_from_request(
        input_filename="chart-request.json",
        output_filename="june_financial_breakdown.png",
    )

    assert Path(output_path).exists()
    assert Path(output_path).suffix.lower() == ".png"
    assert "AI rendered approved bar chart to june_financial_breakdown.png inside AI_Workspace." in log_path.read_text(encoding="utf-8")


def test_generate_chart_request_returns_schema_validated_payload(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(local_ai_finance, "WORKSPACE_DIR", tmp_path)
    log_path = tmp_path / "ai_activity.log"
    monkeypatch.setattr(local_ai_finance, "LOG_FILE", log_path)
    local_ai_finance.ensure_workspace()
    chart_source = tmp_path / "summary.csv"
    chart_source.write_text("Category,Amount\nSoftware,540\nRent,1200\n", encoding="utf-8")

    monkeypatch.setattr(local_ai_finance, "check_ollama_available", lambda *args, **kwargs: (True, None))
    monkeypatch.setattr(local_ai_finance, "load_system_prompt", lambda: "system prompt")
    original_load_json_file = local_ai_finance.load_json_file

    def fake_load_json_file(path):
        if Path(path) == local_ai_finance.LOCAL_MODEL_PROFILE_CONFIG_PATH:
            return {"profiles": {"chat": {"model": "mock-model"}}}
        return original_load_json_file(path)

    monkeypatch.setattr(local_ai_finance, "load_json_file", fake_load_json_file)
    monkeypatch.setattr(local_ai_finance, "resolve_profile", lambda config, alias: {"model": "mock-model", "seed": 7})
    monkeypatch.setattr(local_ai_finance, "build_options", lambda profile, seed=None: {})

    captured: dict[str, object] = {}

    def fake_run_ollama_generate_with_schema(**kwargs):
        captured.update(kwargs)
        return {
            "chart_config": {
                "chart_type": "bar",
                "title": "Overhead Variance",
                "x_axis_label": "Category",
                "y_axis_label": "Amount",
            },
            "chart_data": [
                {"label": "Software", "value": 540.0},
                {"label": "Rent", "value": 1200.0},
            ],
        }

    monkeypatch.setattr(local_ai_finance, "run_ollama_generate_with_schema", fake_run_ollama_generate_with_schema)

    payload = local_ai_finance.generate_chart_request(
        user_request="Create a bar chart showing overhead variance by category.",
        filename="summary.csv",
        profile_alias="chat",
        timeout_seconds=30,
        processing_limit=12,
    )

    assert payload["chart_config"]["chart_type"] == "bar"
    assert len(payload["chart_data"]) == 2
    assert "Structured response mode is now active." in str(captured["prompt"])
    assert "Mute all conversational personality" in str(captured["prompt"])
    assert "AI intent: Generate structured chart JSON from prompt" in log_path.read_text(encoding="utf-8")


def test_generate_and_render_chart_runs_combined_reviewed_workflow(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(local_ai_finance, "WORKSPACE_DIR", tmp_path)
    log_path = tmp_path / "ai_activity.log"
    monkeypatch.setattr(local_ai_finance, "LOG_FILE", log_path)
    local_ai_finance.ensure_workspace()

    monkeypatch.setattr(
        local_ai_finance,
        "generate_chart_request",
        lambda **kwargs: {
            "chart_config": {
                "chart_type": "bar",
                "title": "Overhead Variance",
                "x_axis_label": "Category",
                "y_axis_label": "Amount",
            },
            "chart_data": [
                {"label": "Software", "value": 540.0},
                {"label": "Rent", "value": 1200.0},
            ],
        },
    )
    monkeypatch.setattr(local_ai_finance, "review_step", lambda plan_text: None)

    output_path = local_ai_finance.generate_and_render_chart(
        user_request="Create a bar chart showing overhead variance by category.",
        output_filename="overhead_variance.png",
        filename=None,
        profile_alias="chat",
        timeout_seconds=30,
        processing_limit=12,
    )

    generated_request_candidates = list(tmp_path.glob("*-overhead-variance-generated-chart-request.json"))
    assert len(generated_request_candidates) == 1
    generated_request_path = generated_request_candidates[0]
    assert generated_request_path.exists()
    assert Path(output_path).exists()
    assert Path(output_path).suffix.lower() == ".png"
    assert Path(output_path).name.endswith("-overhead-variance.png")
    log_text = log_path.read_text(encoding="utf-8")
    assert f"AI wrote reviewed chart_render_request JSON export to {generated_request_path.name} inside AI_Workspace." in log_text
    assert f"AI rendered approved bar chart to {Path(output_path).name} inside AI_Workspace." in log_text


def test_apply_chart_request_guardrails_flags_duplicate_labels_and_negative_pie_values() -> None:
    payload = {
        "chart_config": {
            "chart_type": "pie",
            "title": "Overhead Mix",
            "x_axis_label": "Category",
            "y_axis_label": "Amount",
            "highlight_label": "Software",
        },
        "chart_data": [
            {"label": "Software", "value": 540.0},
            {"label": "software", "value": -25.0},
        ],
    }

    guarded = local_ai_finance.apply_chart_request_guardrails(payload)

    assert guarded["flag_for_review"] is True
    assert "duplicates" in guarded["review_reason"]
    assert "Pie charts cannot include negative values." in guarded["alert_reason"]


def test_build_chart_preview_summary_includes_alert_and_output() -> None:
    payload = {
        "chart_config": {
            "chart_type": "bar",
            "title": "Variance Review",
            "x_axis_label": "Category",
            "y_axis_label": "Amount",
        },
        "chart_data": [{"label": "Software", "value": 540.0}],
        "flag_for_review": True,
        "review_reason": "Duplicate labels require review.",
        "alert_reason": "Potential anomaly detected.",
    }

    summary = local_ai_finance.build_chart_preview_summary(payload, output_filename="2026-06-16-variance-review.png")

    assert "Chart preview: Variance Review" in summary
    assert "Planned output: 2026-06-16-variance-review.png" in summary
    assert "Review required: Duplicate labels require review." in summary
    assert "[ALERT] Potential anomaly detected." in summary