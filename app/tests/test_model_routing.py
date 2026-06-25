from __future__ import annotations

import pytest

from app import ai_local_config as config
from app.tests.lane_routing_test_helpers import (
    BACKEND_LANE_URL,
    EVALUATOR_LANE_URL,
    FRONTEND_LANE_URL,
)


@pytest.fixture(autouse=True)
def _clear_ai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AI_FRONTEND_BASE_URL",
        "AI_BACKEND_BASE_URL",
        "AI_FRONTEND_MODEL",
        "AI_BACKEND_MODEL",
        "OLLAMA_BASE_URL",
        "OLLAMA_FRONTEND_BASE_URL",
        "OLLAMA_BACKEND_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_profile_base_url_resolves_by_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FRONTEND_BASE_URL", "http://frontend:11434")
    monkeypatch.setenv("AI_BACKEND_BASE_URL", "http://backend:11435")

    assert config.resolve_profile_base_url("chat") == "http://frontend:11434"
    assert config.resolve_profile_base_url("coder") == "http://backend:11435"
    assert config.resolve_profile_base_url("chat_second_opinion") == "http://backend:11435"


def test_profile_base_url_honors_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FRONTEND_BASE_URL", "http://frontend:11434")
    monkeypatch.setenv("AI_BACKEND_BASE_URL", "http://backend:11435")

    assert config.resolve_profile_base_url("coder", override_base_url="http://override:9999/v1") == "http://override:9999"


def test_get_model_for_profile_alias_uses_lane_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FRONTEND_MODEL", "frontend-24b")
    monkeypatch.setenv("AI_BACKEND_MODEL", "backend-30b")

    assert config.get_model_for_profile_alias("chat") == "frontend-24b"
    assert config.get_model_for_profile_alias("coder") == "backend-30b"
    assert config.get_model_for_profile_alias("chat_second_opinion") == "backend-30b"


def test_resolve_lane_base_urls_for_ab_eval_script() -> None:
    import importlib.util
    from pathlib import Path

    script_path = Path(__file__).resolve().parents[2] / "scripts" / "run_local_model_ab_eval.py"
    spec = importlib.util.spec_from_file_location("run_local_model_ab_eval", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    profile_a_url, profile_b_url = module._resolve_lane_base_urls("chat", "chat_second_opinion", "")

    assert profile_a_url == config.get_frontend_base_url()
    assert profile_b_url == config.get_backend_base_url()


def test_litellm_frontend_alias_resolves_to_frontend_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FRONTEND_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("AI_BACKEND_BASE_URL", "http://127.0.0.1:11435")

    assert config.resolve_litellm_api_base_url("hal-chat-balanced") == "http://127.0.0.1:11434"
    assert config.resolve_profile_base_url("chat") == "http://127.0.0.1:11434"


def test_litellm_backend_aliases_resolve_to_backend_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FRONTEND_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("AI_BACKEND_BASE_URL", "http://127.0.0.1:11435")

    assert config.resolve_litellm_api_base_url("hal-coding") == "http://127.0.0.1:11435"
    assert config.resolve_litellm_api_base_url("hal-second-opinion") == "http://127.0.0.1:11435"
    assert config.resolve_profile_base_url("coder") == "http://127.0.0.1:11435"
    assert config.resolve_profile_base_url("chat_second_opinion") == "http://127.0.0.1:11435"


def test_control_routes_resolve_lane_urls_dynamically(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.control_routes as control_routes

    monkeypatch.setenv("AI_FRONTEND_BASE_URL", "http://dynamic-frontend:11434")
    monkeypatch.setenv("AI_BACKEND_BASE_URL", "http://dynamic-backend:11435")

    assert control_routes._base_url_for_task_kind("chat") == "http://dynamic-frontend:11434"
    assert control_routes._base_url_for_task_kind("second_opinion") == "http://dynamic-backend:11435"


def test_normal_aliases_never_resolve_to_evaluator_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FRONTEND_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("AI_BACKEND_BASE_URL", "http://127.0.0.1:11435")

    aliases = (
        *config.FRONTEND_PROFILE_ALIASES,
        *config.BACKEND_PROFILE_ALIASES,
        *config.LITELLM_FRONTEND_ALIASES,
        *config.LITELLM_BACKEND_ALIASES,
    )
    evaluator_url = config.get_evaluator_base_url()
    for alias in aliases:
        if alias in config.LITELLM_FRONTEND_ALIASES | config.LITELLM_BACKEND_ALIASES:
            resolved = config.resolve_litellm_api_base_url(alias)
        else:
            resolved = config.resolve_profile_base_url(alias)
        assert resolved != evaluator_url
        assert ":11436" not in resolved


def test_chat_profile_never_resolves_to_backend_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FRONTEND_BASE_URL", FRONTEND_LANE_URL)
    monkeypatch.setenv("AI_BACKEND_BASE_URL", BACKEND_LANE_URL)

    chat_url = config.resolve_profile_base_url("chat")
    assert ":11434" in chat_url
    assert ":11435" not in chat_url
    assert chat_url != BACKEND_LANE_URL


def test_backend_profiles_never_resolve_to_frontend_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FRONTEND_BASE_URL", FRONTEND_LANE_URL)
    monkeypatch.setenv("AI_BACKEND_BASE_URL", BACKEND_LANE_URL)

    for alias in config.BACKEND_PROFILE_ALIASES:
        resolved = config.resolve_profile_base_url(alias)
        assert ":11435" in resolved
        assert ":11434" not in resolved
        assert resolved != FRONTEND_LANE_URL


def test_normal_profiles_never_resolve_to_evaluator_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_EVALUATOR_BASE_URL", EVALUATOR_LANE_URL)
    monkeypatch.setenv("AI_FRONTEND_BASE_URL", FRONTEND_LANE_URL)
    monkeypatch.setenv("AI_BACKEND_BASE_URL", BACKEND_LANE_URL)

    for alias in config.FRONTEND_PROFILE_ALIASES | config.BACKEND_PROFILE_ALIASES:
        assert config.resolve_profile_base_url(alias) != EVALUATOR_LANE_URL
