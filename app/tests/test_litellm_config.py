from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app import ai_local_config as config


LITELLM_CONFIG_PATH = Path(__file__).resolve().parents[2] / "scripts" / "litellm_ollama_router.yaml"


@pytest.fixture(autouse=True)
def _clear_ai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AI_FRONTEND_BASE_URL",
        "AI_BACKEND_BASE_URL",
        "OLLAMA_FRONTEND_BASE_URL",
        "OLLAMA_BACKEND_BASE_URL",
        "OLLAMA_BASE_URL",
        "OLLAMA_EVALUATOR_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def _load_litellm_router_config() -> dict:
    return yaml.safe_load(LITELLM_CONFIG_PATH.read_text(encoding="utf-8"))


def test_litellm_yaml_splits_frontend_and_backend_api_base() -> None:
    payload = _load_litellm_router_config()
    by_alias: dict[str, str] = {}
    for entry in payload["model_list"]:
        by_alias[entry["model_name"]] = entry["litellm_params"]["api_base"]

    assert by_alias["hal-chat-balanced"] == "os.environ/OLLAMA_FRONTEND_BASE_URL"
    assert by_alias["hal-vision"] == "os.environ/OLLAMA_FRONTEND_BASE_URL"
    assert by_alias["hal-coding"] == "os.environ/OLLAMA_BACKEND_BASE_URL"
    assert by_alias["hal-analysis"] == "os.environ/OLLAMA_BACKEND_BASE_URL"
    assert by_alias["hal-second-opinion"] == "os.environ/OLLAMA_BACKEND_BASE_URL"

    env_vars = payload["environment_variables"]
    assert env_vars["OLLAMA_FRONTEND_BASE_URL"] == "http://127.0.0.1:11434"
    assert env_vars["OLLAMA_BACKEND_BASE_URL"] == "http://127.0.0.1:11435"
    assert ":11436" not in yaml.safe_dump(payload)


def test_litellm_alias_resolution_uses_lane_specific_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FRONTEND_BASE_URL", "http://frontend:11434")
    monkeypatch.setenv("AI_BACKEND_BASE_URL", "http://backend:11435")

    assert config.resolve_litellm_api_base_url("hal-chat-balanced") == "http://frontend:11434"
    assert config.resolve_litellm_api_base_url("hal-vision") == "http://frontend:11434"
    assert config.resolve_litellm_api_base_url("hal-coding") == "http://backend:11435"
    assert config.resolve_litellm_api_base_url("hal-analysis") == "http://backend:11435"
    assert config.resolve_litellm_api_base_url("hal-second-opinion") == "http://backend:11435"
    assert config.resolve_profile_base_url("chat_second_opinion") == "http://backend:11435"


def test_litellm_environment_overrides_are_lane_specific(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_FRONTEND_BASE_URL", "http://override-frontend:11434")
    monkeypatch.setenv("OLLAMA_BACKEND_BASE_URL", "http://override-backend:11435")

    env_vars = config.build_litellm_environment_variables(proxy_base_url="http://127.0.0.1:4000")

    assert env_vars["OLLAMA_FRONTEND_BASE_URL"] == "http://override-frontend:11434"
    assert env_vars["OLLAMA_BACKEND_BASE_URL"] == "http://override-backend:11435"
    assert env_vars["OLLAMA_BASE_URL"] == "http://override-frontend:11434"
    assert env_vars["LITELLM_PROXY_BASE_URL"] == "http://127.0.0.1:4000"
    assert ":11436" not in str(env_vars.values())


def test_normal_litellm_aliases_do_not_use_evaluator_lane() -> None:
    for alias in config.LITELLM_FRONTEND_ALIASES | config.LITELLM_BACKEND_ALIASES:
        resolved = config.resolve_litellm_api_base_url(alias)
        assert ":11436" not in resolved
        assert resolved != config.get_evaluator_base_url()
