from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest

from app import ai_local_config as config
import app.hal.orchestrator as hal_orchestrator
from app.ai_local_config import LocalAIConfigError


@pytest.fixture(autouse=True)
def _clear_ai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AI_FRONTEND_BASE_URL",
        "AI_BACKEND_BASE_URL",
        "AI_FRONTEND_MODEL",
        "AI_BACKEND_MODEL",
        "OLLAMA_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def _hal_runtime_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_dir = os.path.join(os.path.dirname(__file__), ".second_opinion_runtime", uuid4().hex)
    os.environ["HAL_ALLOWED_BASE_PATH"] = runtime_dir
    os.environ["HAL_SQLITE_PATH"] = os.path.join(runtime_dir, "hal_test.sqlite3")
    os.environ["HAL_CHROMA_PATH"] = os.path.join(runtime_dir, "hal_chroma")


def test_resolve_lane_profile_chat_second_opinion_uses_backend_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_BACKEND_BASE_URL", "http://backend:11435")
    monkeypatch.setenv("AI_BACKEND_MODEL", "backend-30b")

    payload = config.load_local_model_profile_config()
    profile = config.resolve_lane_profile(payload, "chat_second_opinion")

    assert config.profile_lane("chat_second_opinion") == "backend"
    assert config.resolve_profile_base_url("chat_second_opinion") == "http://backend:11435"
    assert config.get_model_for_profile_alias("chat_second_opinion") == "backend-30b"
    assert profile["model"] == "backend-30b"


def test_second_opinion_calls_backend_lane_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_BACKEND_BASE_URL", "http://127.0.0.1:11435")
    monkeypatch.setenv("AI_BACKEND_MODEL", "qwen3:30b")

    captured: dict[str, object] = {}

    def fake_require_lane_runtime(alias, *, purpose):
        assert alias == "chat_second_opinion"
        captured["base_url"] = config.get_backend_base_url()
        return captured["base_url"]

    def fake_generate_response_result(*, base_url, profile, prompt, timeout_seconds, seed=None):
        captured["base_url"] = base_url
        captured["profile"] = profile
        captured["prompt"] = prompt
        return {"response_text": "Backend second opinion on collections risk."}

    monkeypatch.setattr(hal_orchestrator, "require_lane_runtime", fake_require_lane_runtime)
    monkeypatch.setattr(hal_orchestrator, "generate_response_result", fake_generate_response_result)
    monkeypatch.setattr(hal_orchestrator, "retrieve_relevant_context", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "get_live_financial_context", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_hardware_snippets", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_softdent_aggregate_snippets", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_live_report_snippets", lambda question: [])
    monkeypatch.setattr(
        hal_orchestrator,
        "get_controlled_patient_context",
        lambda question: {"matched": False, "snippets": [], "narrative": ""},
    )

    payload = hal_orchestrator.answer_hal_second_opinion_question(
        question="Give me a deeper second opinion on collections risk.",
        actor="hal_operator",
        summary={"latestDailyKpi": {"gross_production": 7759}},
    )

    assert payload["mode"] == "local-rag-phase-1:second-opinion"
    assert payload["answer"] == "Backend second opinion on collections risk."
    assert payload["local_ai_unavailable"] is None
    assert captured["base_url"] == "http://127.0.0.1:11435"
    assert captured["profile"]["model"] == "qwen3:30b"
    assert "7759" in str(captured["prompt"])
    assert "backend second-opinion model required" in payload["guardrails"]


def test_hal_chat_stays_deterministic_without_local_ai_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_generate(*args, **kwargs):
        raise AssertionError("HAL chat must not call generate_response_result")

    monkeypatch.setattr(hal_orchestrator, "generate_response_result", fail_generate)
    monkeypatch.setattr(hal_orchestrator, "retrieve_relevant_context", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "get_live_financial_context", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_hardware_snippets", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_softdent_aggregate_snippets", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_live_report_snippets", lambda question: [])
    monkeypatch.setattr(
        hal_orchestrator,
        "get_controlled_patient_context",
        lambda question: {"matched": False, "snippets": [], "narrative": ""},
    )

    payload = hal_orchestrator.answer_hal_question(
        question="What matters most this morning?",
        actor="hal_operator",
    )

    assert payload["mode"] == "local-rag-phase-1"
    assert "deterministic server facts first" in payload["guardrails"]


def test_coder_profile_still_resolves_to_backend_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_BACKEND_BASE_URL", "http://127.0.0.1:11435")
    monkeypatch.setenv("AI_BACKEND_MODEL", "qwen3:30b")

    assert config.resolve_profile_base_url("coder") == "http://127.0.0.1:11435"
    assert config.get_model_for_profile_alias("coder") == "qwen3:30b"


def test_hal_chat_still_resolves_to_frontend_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FRONTEND_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("AI_FRONTEND_MODEL", "mistral-small3.1:24b")

    assert config.resolve_profile_base_url("chat") == "http://127.0.0.1:11434"
    assert config.get_model_for_profile_alias("chat") == "mistral-small3.1:24b"


def test_second_opinion_backend_unavailable_returns_explicit_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_require_lane_runtime(alias, *, purpose):
        raise LocalAIConfigError(
            "Local AI runtime unavailable for HAL second opinion. "
            "Lane=backend, model=qwen3:30b, base_url=http://127.0.0.1:11435. connection refused"
        )

    monkeypatch.setattr(hal_orchestrator, "require_lane_runtime", fake_require_lane_runtime)
    monkeypatch.setattr(hal_orchestrator, "generate_response_result", lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not generate")))
    monkeypatch.setattr(hal_orchestrator, "retrieve_relevant_context", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "get_live_financial_context", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_hardware_snippets", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_softdent_aggregate_snippets", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_live_report_snippets", lambda question: [])
    monkeypatch.setattr(
        hal_orchestrator,
        "get_controlled_patient_context",
        lambda question: {"matched": False, "snippets": [], "narrative": ""},
    )

    payload = hal_orchestrator.answer_hal_second_opinion_question(
        question="Give me a deeper second opinion on collections risk.",
        actor="hal_operator",
    )

    assert payload["answer"].startswith("Second opinion unavailable.")
    assert payload["local_ai_unavailable"] is not None
    assert "Backend local AI lane unavailable" in payload["local_ai_unavailable"]
    assert "no deterministic fallback when backend unavailable" in payload["guardrails"]
    assert payload["answer"] != payload.get("narrative")
