from __future__ import annotations

from pathlib import Path

import pytest

from app import ai_local_config as config

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
ISOLATED_SECTION_SCRIPT = SCRIPTS_DIR / "run_235b_isolated_section.ps1"
START_EVALUATOR_SCRIPT = SCRIPTS_DIR / "start_235b_evaluator_lane.ps1"
STOP_EVALUATOR_SCRIPT = SCRIPTS_DIR / "stop_235b_evaluator_lane.ps1"
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
    assert config.DEFAULT_FRONTEND_MODEL == "qwen3:14b"
    assert config.DEFAULT_BACKEND_MODEL == "qwen3:14b"
    assert config.get_frontend_model_name() == "qwen3:14b"
    assert config.get_backend_model_name() == "qwen3:14b"


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

    assert "qwen3:14b" in defaults_ps1
    assert "qwen3:14b" in defaults_sh
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
    assert "AI_FRONTEND_MODEL=qwen3:14b" in env_example
    assert "AI_BACKEND_MODEL=qwen3:14b" in env_example
    assert "# AI_FRONTEND_MODEL=frontend-24b-q4" in env_example
    assert "# AI_BACKEND_MODEL=backend-30b-q4" in env_example


def test_normal_run_scripts_do_not_use_evaluator_port() -> None:
    for script_name in NORMAL_RUN_SCRIPTS:
        script_text = (SCRIPTS_DIR / script_name).read_text(encoding="utf-8")
        assert ":11436" not in script_text


def test_isolated_section_script_runs_one_section_only() -> None:
    script_text = ISOLATED_SECTION_SCRIPT.read_text(encoding="utf-8")
    assert "ValidateSet('1', '2', '3', '4', '5')" in script_text
    assert "run_235b_eval_section.py" in script_text
    assert "Does not run multiple sections" in script_text


def test_isolated_section_script_stops_normal_lanes_before_evaluator() -> None:
    script_text = ISOLATED_SECTION_SCRIPT.read_text(encoding="utf-8")
    stop_index = script_text.index("stop_normal_model_lanes.ps1")
    start_eval_index = script_text.index("start_235b_evaluator_lane.ps1")
    verify_normal_down_index = script_text.index("Verify :11434 and :11435 are down")
    assert stop_index < verify_normal_down_index < start_eval_index
    assert "Normal lanes still respond" in script_text


def test_restart_normal_lanes_is_opt_in() -> None:
    script_text = ISOLATED_SECTION_SCRIPT.read_text(encoding="utf-8")
    assert "[switch]$RestartNormalLanes" in script_text
    assert "if ($RestartNormalLanes)" in script_text
    assert "Skipping normal lane restart" in script_text


def test_force_stop_ollama_app_is_opt_in() -> None:
    for script_path in (ISOLATED_SECTION_SCRIPT, STOP_EVALUATOR_SCRIPT):
        script_text = script_path.read_text(encoding="utf-8")
        assert "[switch]$ForceStopOllamaApp" in script_text
        assert "if ($ForceStopOllamaApp)" in script_text


def test_start_evaluator_requires_normal_lanes_down() -> None:
    script_text = START_EVALUATOR_SCRIPT.read_text(encoding="utf-8")
    assert "127.0.0.1:11434" in script_text
    assert "127.0.0.1:11435" in script_text
    assert "Normal lanes must be stopped before starting the 235B evaluator" in script_text
    assert "stop_normal_model_lanes.ps1" in script_text
