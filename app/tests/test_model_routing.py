from __future__ import annotations

import pytest

from app import ai_local_config as config


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
