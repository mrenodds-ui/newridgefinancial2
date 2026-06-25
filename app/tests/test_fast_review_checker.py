from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import ai_local_config as config
from app.hal import fast_review_checker as checker
from app.tests.lane_routing_test_helpers import (
    BACKEND_LANE_URL,
    EVALUATOR_LANE_URL,
    FAST_REVIEW_LANE_URL,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"
SAMPLE_PACKET = PROJECT_ROOT / "evals" / "insurance_narrative_packets" / "sample_crown_denial.json"


@pytest.fixture(autouse=True)
def _clear_ai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AI_BACKEND_BASE_URL",
        "AI_FAST_REVIEW_BASE_URL",
        "AI_FAST_REVIEW_MODEL",
        "OLLAMA_FAST_REVIEW_BASE_URL",
        "OLLAMA_FAST_REVIEW_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)


def _valid_review_json() -> str:
    return json.dumps(
        {
            "missing_data": ["accounts receivable export"],
            "citation_issues": [],
            "possible_invented_facts": [],
            "contradictions": [],
            "recommended_action": "Request missing attachment before resubmission.",
            "ready_for_human_review": True,
        }
    )


def test_fast_review_checker_resolves_fast_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FAST_REVIEW_BASE_URL", FAST_REVIEW_LANE_URL)

    target = checker._resolve_fast_review_target()

    assert target["profile"] == "fast_review"
    assert target["base_url"] == FAST_REVIEW_LANE_URL
    assert ":11437" in target["base_url"]
    assert ":11435" not in target["base_url"]
    assert target["model"] == config.DEFAULT_FAST_REVIEW_MODEL


def test_chat_second_opinion_still_resolves_backend_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_BACKEND_BASE_URL", BACKEND_LANE_URL)

    assert config.resolve_profile_base_url("chat_second_opinion") == BACKEND_LANE_URL
    assert config.get_model_for_profile_alias("chat_second_opinion") == config.DEFAULT_BACKEND_MODEL


def test_checker_never_targets_evaluator_lane() -> None:
    with pytest.raises(checker.FastReviewCheckerError):
        checker.assert_fast_review_lane_url(EVALUATOR_LANE_URL)


def test_run_fast_review_check_lane_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FAST_REVIEW_BASE_URL", FAST_REVIEW_LANE_URL)
    monkeypatch.setattr(checker, "check_lane_runtime_available", lambda alias: (False, "connection refused"))

    calls: list[tuple[str, str]] = []

    def fail_generate(**kwargs):
        calls.append(("generate", str(kwargs.get("base_url"))))
        raise AssertionError("must not call model when lane is unavailable")

    monkeypatch.setattr(checker, "generate_response_result", fail_generate)

    result = checker.run_fast_review_check(
        source_text="De-identified sample packet for review.",
        review_task="insurance_narrative_review",
        packet_id="sample",
        actor="tester",
    )

    assert result["status"] == "lane_unavailable"
    assert result["profile"] == "fast_review"
    assert result["base_url"] == FAST_REVIEW_LANE_URL
    assert result["error"] == "connection refused"
    assert result["review"] is None
    assert calls == []
    assert "no chat_second_opinion fallback" in result["guardrails"]


def test_run_fast_review_check_uses_fast_lane_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FAST_REVIEW_BASE_URL", FAST_REVIEW_LANE_URL)
    monkeypatch.setattr(checker, "check_lane_runtime_available", lambda alias: (True, None))

    seen_base_urls: list[str] = []

    def fake_generate(*, base_url: str, profile, prompt: str, timeout_seconds: int, seed=None):
        seen_base_urls.append(base_url)
        assert ":11437" in base_url
        assert ":11435" not in base_url
        assert ":11436" not in base_url
        return {"response_text": _valid_review_json(), "metrics": {}}

    monkeypatch.setattr(checker, "generate_response_result", fake_generate)

    packet = json.loads(SAMPLE_PACKET.read_text(encoding="utf-8"))
    result = checker.run_fast_review_check(
        source_text=str(packet["source_text"]),
        review_task=str(packet.get("review_task") or "insurance_narrative_review"),
        packet_id=str(packet.get("id")),
        actor="tester",
    )

    assert result["status"] == "ok"
    assert result["profile"] == "fast_review"
    assert result["base_url"] == FAST_REVIEW_LANE_URL
    assert seen_base_urls == [FAST_REVIEW_LANE_URL]
    assert result["review"]["ready_for_human_review"] is True
    assert "missing_data" in result["review"]


def test_parse_fast_review_structured_output_enforces_keys() -> None:
    with pytest.raises(Exception, match="Missing required JSON keys"):
        checker.parse_fast_review_structured_output('{"missing_data": []}')

    with pytest.raises(Exception, match="ready_for_human_review must be a boolean"):
        checker.parse_fast_review_structured_output(
            json.dumps(
                {
                    "missing_data": [],
                    "citation_issues": [],
                    "possible_invented_facts": [],
                    "contradictions": [],
                    "recommended_action": "review",
                    "ready_for_human_review": "yes",
                }
            )
        )

    parsed = checker.parse_fast_review_structured_output(_valid_review_json())
    assert set(parsed.keys()) == set(checker.FAST_REVIEW_REQUIRED_KEYS)


def test_env_example_documents_ollama_fallback_tag() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "AI_FAST_REVIEW_MODEL=qwen3-coder:30b" in text
    assert "Qwen3-Coder-30B-A3B-Instruct" in text


def test_default_fast_review_model_is_ollama_tag() -> None:
    assert config.DEFAULT_FAST_REVIEW_MODEL == "qwen3-coder:30b"
    assert config.get_fast_review_model_name() == "qwen3-coder:30b"
