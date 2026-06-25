from __future__ import annotations

from pathlib import Path

import pytest

from app import ai_local_config as config


@pytest.fixture(autouse=True)
def _clear_ai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AI_RUNTIME",
        "AI_FRONTEND_BASE_URL",
        "AI_BACKEND_BASE_URL",
        "AI_FRONTEND_MODEL",
        "AI_BACKEND_MODEL",
        "AI_FRONTEND_MODEL_PATH",
        "AI_BACKEND_MODEL_PATH",
        "AI_CONTEXT_SIZE",
        "AI_FRONTEND_CONTEXT_SIZE",
        "AI_BACKEND_CONTEXT_SIZE",
        "AI_GPU_LAYERS",
        "OLLAMA_BASE_URL",
        "OLLAMA_BACKEND_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_frontend_and_backend_resolve_separately(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FRONTEND_BASE_URL", "http://frontend:11434")
    monkeypatch.setenv("AI_BACKEND_BASE_URL", "http://backend:11435")
    monkeypatch.setenv("AI_FRONTEND_MODEL", "frontend-24b-q4")
    monkeypatch.setenv("AI_BACKEND_MODEL", "backend-30b-q4")

    assert config.get_frontend_base_url() == "http://frontend:11434"
    assert config.get_backend_base_url() == "http://backend:11435"
    assert config.get_frontend_model_name() == "frontend-24b-q4"
    assert config.get_backend_model_name() == "backend-30b-q4"


def test_profile_lane_routing_uses_expected_models(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = config.load_local_model_profile_config()

    frontend_profile = config.resolve_lane_profile(payload, "chat")
    backend_profile = config.resolve_lane_profile(payload, "coder")

    assert config.profile_lane("chat") == "frontend"
    assert config.profile_lane("coder") == "backend"
    assert frontend_profile["model"] == config.DEFAULT_FRONTEND_MODEL
    assert backend_profile["model"] == config.DEFAULT_BACKEND_MODEL
    assert frontend_profile["gguf_quant"] == config.DEFAULT_FRONTEND_QUANT
    assert backend_profile["gguf_quant"] == config.DEFAULT_BACKEND_QUANT


def test_env_overrides_model_name_and_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_FRONTEND_MODEL", "ollama-frontend")
    monkeypatch.setenv("OLLAMA_BACKEND_MODEL", "ollama-backend")
    assert config.get_frontend_model_name() == "ollama-frontend"
    assert config.get_backend_model_name() == "ollama-backend"

    monkeypatch.setenv("AI_FRONTEND_MODEL", "custom-24b")
    monkeypatch.setenv("AI_BACKEND_MODEL", "custom-30b")
    monkeypatch.setenv("AI_FRONTEND_CONTEXT_SIZE", "8192")
    monkeypatch.setenv("AI_BACKEND_CONTEXT_SIZE", "2048")

    payload = config.load_local_model_profile_config()
    frontend_profile = config.resolve_lane_profile(payload, "chat")
    backend_profile = config.resolve_lane_profile(payload, "chat_second_opinion")

    assert frontend_profile["model"] == "custom-24b"
    assert backend_profile["model"] == "custom-30b"
    assert frontend_profile["num_ctx"] == 8192
    assert backend_profile["num_ctx"] == 2048


def test_missing_llama_cpp_paths_raise_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_RUNTIME", "llama_cpp")

    with pytest.raises(config.LocalAIConfigError, match="AI_FRONTEND_MODEL_PATH"):
        config.validate_local_model_paths()


def test_missing_llama_cpp_file_raises_clear_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI_RUNTIME", "llama_cpp")
    monkeypatch.setenv("AI_FRONTEND_MODEL_PATH", str(tmp_path / "missing.gguf"))
    monkeypatch.setenv("AI_BACKEND_MODEL_PATH", str(tmp_path / "also-missing.gguf"))

    with pytest.raises(config.LocalAIConfigError, match="missing.gguf"):
        config.validate_local_model_paths()


def test_openai_compatible_base_url_strips_v1_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FRONTEND_BASE_URL", "http://127.0.0.1:11434/v1")
    assert config.get_frontend_base_url() == "http://127.0.0.1:11434"


def test_model_routing_snapshot_includes_both_lanes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FRONTEND_MODEL", "lane-a")
    monkeypatch.setenv("AI_BACKEND_MODEL", "lane-b")

    snapshot = config.get_model_routing_snapshot()
    assert snapshot["frontend"]["model"] == "lane-a"
    assert snapshot["backend"]["model"] == "lane-b"
    assert "chat" in snapshot["frontend"]["profile_aliases"]
    assert "coder" in snapshot["backend"]["profile_aliases"]


def test_gitignore_blocks_model_artifacts() -> None:
    gitignore = (Path(__file__).resolve().parents[2] / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("models/", ".local_models/", "*.gguf"):
        assert pattern in gitignore


def test_require_lane_runtime_raises_clear_message_when_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FRONTEND_BASE_URL", "http://127.0.0.1:59999")

    def fake_check(*args, **kwargs):
        return False, "connection refused"

    monkeypatch.setattr(config, "check_lane_runtime_available", fake_check)

    with pytest.raises(config.LocalAIConfigError, match="document RAG"):
        config.require_lane_runtime("chat", purpose="document RAG answer generation")


def test_base_url_resolvers_read_env_after_module_import(monkeypatch: pytest.MonkeyPatch) -> None:
    assert config.get_frontend_base_url() == config.DEFAULT_FRONTEND_BASE_URL
    assert config.get_backend_base_url() == config.DEFAULT_BACKEND_BASE_URL

    monkeypatch.setenv("AI_FRONTEND_BASE_URL", "http://dynamic-frontend:11434")
    monkeypatch.setenv("AI_BACKEND_BASE_URL", "http://dynamic-backend:11435")

    assert config.get_frontend_base_url() == "http://dynamic-frontend:11434"
    assert config.get_backend_base_url() == "http://dynamic-backend:11435"
    assert config.resolve_profile_base_url("chat") == "http://dynamic-frontend:11434"
    assert config.resolve_profile_base_url("coder") == "http://dynamic-backend:11435"


def test_legacy_ollama_base_url_affects_frontend_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_FRONTEND_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_FRONTEND_BASE_URL", raising=False)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://legacy-frontend:11434")

    assert config.get_frontend_base_url() == "http://legacy-frontend:11434"
    assert config.get_backend_base_url() == config.DEFAULT_BACKEND_BASE_URL
    assert config.resolve_profile_base_url("chat_second_opinion") == config.DEFAULT_BACKEND_BASE_URL


def test_evaluator_url_is_isolated_from_normal_profiles(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_EVALUATOR_BASE_URL", "http://evaluator:11436")
    monkeypatch.setenv("AI_FRONTEND_BASE_URL", "http://frontend:11434")
    monkeypatch.setenv("AI_BACKEND_BASE_URL", "http://backend:11435")

    assert config.get_evaluator_base_url() == "http://evaluator:11436"
    assert config.resolve_profile_base_url("chat") == "http://frontend:11434"
    assert config.resolve_profile_base_url("coder") == "http://backend:11435"
    assert config.resolve_profile_base_url("chat") != config.get_evaluator_base_url()
    assert config.resolve_profile_base_url("coder") != config.get_evaluator_base_url()


def test_resolve_lane_profile_picks_up_env_changes_after_import(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = config.load_local_model_profile_config()

    monkeypatch.setenv("AI_FRONTEND_MODEL", "dynamic-frontend-model")
    monkeypatch.setenv("AI_BACKEND_MODEL", "dynamic-backend-model")

    frontend_profile = config.resolve_lane_profile(payload, "chat")
    backend_profile = config.resolve_lane_profile(payload, "chat_second_opinion")

    assert frontend_profile["model"] == "dynamic-frontend-model"
    assert backend_profile["model"] == "dynamic-backend-model"
