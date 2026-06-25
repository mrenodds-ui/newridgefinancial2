from __future__ import annotations

from pathlib import Path

import pytest

from app import ai_local_config as config

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
STALE_DEFAULT_TAGS = ("frontend-24b-q4", "backend-30b-q4")
NORMAL_RUN_SCRIPTS = (
    "run_frontend_model.ps1",
    "run_backend_model.ps1",
    "run_frontend_model.sh",
    "run_backend_model.sh",
    "_local_model_defaults.ps1",
    "ai_model_common.sh",
)


@pytest.fixture(autouse=True)
def _clear_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AI_FRONTEND_MODEL",
        "AI_BACKEND_MODEL",
        "OLLAMA_FRONTEND_MODEL",
        "OLLAMA_BACKEND_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)


def test_app_defaults_match_expected_lane_models() -> None:
    assert config.DEFAULT_FRONTEND_MODEL == "mistral-small3.1:24b"
    assert config.DEFAULT_BACKEND_MODEL == "qwen3:30b"
    assert config.get_frontend_model_name() == "mistral-small3.1:24b"
    assert config.get_backend_model_name() == "qwen3:30b"


def test_model_env_precedence_matches_app_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_FRONTEND_MODEL", "ollama-frontend-tag")
    monkeypatch.setenv("OLLAMA_BACKEND_MODEL", "ollama-backend-tag")
    assert config.get_frontend_model_name() == "ollama-frontend-tag"
    assert config.get_backend_model_name() == "ollama-backend-tag"

    monkeypatch.setenv("AI_FRONTEND_MODEL", "ai-frontend-tag")
    monkeypatch.setenv("AI_BACKEND_MODEL", "ai-backend-tag")
    assert config.get_frontend_model_name() == "ai-frontend-tag"
    assert config.get_backend_model_name() == "ai-backend-tag"


def test_normal_run_scripts_use_app_default_tags() -> None:
    defaults_ps1 = (SCRIPTS_DIR / "_local_model_defaults.ps1").read_text(encoding="utf-8")
    defaults_sh = (SCRIPTS_DIR / "ai_model_common.sh").read_text(encoding="utf-8")
    frontend_script_ps1 = (SCRIPTS_DIR / "run_frontend_model.ps1").read_text(encoding="utf-8")
    backend_script_ps1 = (SCRIPTS_DIR / "run_backend_model.ps1").read_text(encoding="utf-8")
    frontend_script_sh = (SCRIPTS_DIR / "run_frontend_model.sh").read_text(encoding="utf-8")
    backend_script_sh = (SCRIPTS_DIR / "run_backend_model.sh").read_text(encoding="utf-8")

    assert "mistral-small3.1:24b" in defaults_ps1
    assert "qwen3:30b" in defaults_ps1
    assert "mistral-small3.1:24b" in defaults_sh
    assert "qwen3:30b" in defaults_sh
    assert "Get-LocalFrontendModelName" in frontend_script_ps1
    assert "Get-LocalBackendModelName" in backend_script_ps1
    assert "resolve_frontend_model_tag" in frontend_script_sh
    assert "resolve_backend_model_tag" in backend_script_sh

    for script_name in NORMAL_RUN_SCRIPTS:
        script_text = (SCRIPTS_DIR / script_name).read_text(encoding="utf-8")
        for stale_tag in STALE_DEFAULT_TAGS:
            assert stale_tag not in script_text


def test_normal_run_scripts_do_not_default_to_evaluator_model() -> None:
    for script_name in NORMAL_RUN_SCRIPTS:
        script_text = (SCRIPTS_DIR / script_name).read_text(encoding="utf-8")
        assert "qwen3:235b" not in script_text


def test_env_example_documents_actual_default_tags() -> None:
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "AI_FRONTEND_MODEL=mistral-small3.1:24b" in env_example
    assert "AI_BACKEND_MODEL=qwen3:30b" in env_example
    assert "# AI_FRONTEND_MODEL=frontend-24b-q4" in env_example
    assert "# AI_BACKEND_MODEL=backend-30b-q4" in env_example
