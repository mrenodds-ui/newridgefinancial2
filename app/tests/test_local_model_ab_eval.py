from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app import ai_local_config as config
from app.evaluation.ab_compare import run_ab_comparison
from app.tests.lane_routing_test_helpers import BACKEND_LANE_URL, FRONTEND_LANE_URL

REPO_ROOT = Path(__file__).resolve().parents[2]
AB_EVAL_SCRIPT = REPO_ROOT / "scripts" / "run_local_model_ab_eval.py"
AB_CONFIG = {
    "profiles": {
        "chat": {"model": "queen3:14b", "seed": 17},
        "coder": {"model": "queen3:14b", "seed": 31},
        "chat_second_opinion": {"model": "queen3:14b", "seed": 29, "mirostat": 1},
    }
}


@pytest.fixture(autouse=True)
def _clear_lane_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AI_FRONTEND_BASE_URL",
        "AI_BACKEND_BASE_URL",
        "AI_FRONTEND_MODEL",
        "AI_BACKEND_MODEL",
        "OLLAMA_FRONTEND_MODEL",
        "OLLAMA_BACKEND_MODEL",
        "OLLAMA_BASE_URL",
        "OLLAMA_EVALUATOR_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def _load_ab_eval_module():
    spec = importlib.util.spec_from_file_location("run_local_model_ab_eval", AB_EVAL_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_ab_eval_lane_urls_reflect_env_after_config_import(monkeypatch: pytest.MonkeyPatch) -> None:
    assert config.get_frontend_base_url() == config.DEFAULT_FRONTEND_BASE_URL
    monkeypatch.setenv("AI_FRONTEND_BASE_URL", "http://post-import-frontend:11434")
    monkeypatch.setenv("AI_BACKEND_BASE_URL", "http://post-import-backend:11435")
    module = _load_ab_eval_module()

    profile_a_url, profile_b_url = module._resolve_lane_base_urls("chat", "chat_second_opinion", "")

    assert profile_a_url == "http://post-import-frontend:11434"
    assert profile_b_url == "http://post-import-backend:11435"


def test_ab_eval_default_lane_urls_are_profile_specific(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FRONTEND_BASE_URL", "http://frontend:11434")
    monkeypatch.setenv("AI_BACKEND_BASE_URL", "http://backend:11435")
    module = _load_ab_eval_module()

    profile_a_url, profile_b_url = module._resolve_lane_base_urls("chat", "chat_second_opinion", "")

    assert profile_a_url == "http://frontend:11434"
    assert profile_b_url == "http://backend:11435"


def test_ab_eval_legacy_ollama_base_url_env_does_not_auto_override_both_lanes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://legacy-frontend:11434")
    monkeypatch.setenv("AI_BACKEND_BASE_URL", "http://backend:11435")
    module = _load_ab_eval_module()

    profile_a_url, profile_b_url = module._resolve_lane_base_urls("chat", "chat_second_opinion", "")

    assert profile_a_url == "http://legacy-frontend:11434"
    assert profile_b_url == "http://backend:11435"


def test_ab_eval_cli_base_url_override_applies_to_both_profiles(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FRONTEND_BASE_URL", "http://frontend:11434")
    monkeypatch.setenv("AI_BACKEND_BASE_URL", "http://backend:11435")
    module = _load_ab_eval_module()

    profile_a_url, profile_b_url = module._resolve_lane_base_urls(
        "chat",
        "chat_second_opinion",
        "http://override:9999",
    )

    assert profile_a_url == "http://override:9999"
    assert profile_b_url == "http://override:9999"


def test_ab_eval_lane_targets_apply_env_model_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FRONTEND_MODEL", "frontend-env-24b")
    monkeypatch.setenv("AI_BACKEND_MODEL", "backend-env-30b")
    module = _load_ab_eval_module()

    lane_a, lane_b = module._resolve_lane_targets(AB_CONFIG, "chat", "chat_second_opinion", "")

    assert lane_a["lane"] == "frontend"
    assert lane_b["lane"] == "backend"
    assert lane_a["model"] == "frontend-env-24b"
    assert lane_b["model"] == "backend-env-30b"
    assert lane_a["profile"]["model"] == "frontend-env-24b"
    assert lane_b["profile"]["model"] == "backend-env-30b"


def test_ab_eval_default_lane_urls_are_not_collapsed_without_cli_override(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_ab_eval_module()

    profile_a_url, profile_b_url = module._resolve_lane_base_urls("chat", "chat_second_opinion", "")

    assert profile_a_url == config.DEFAULT_FRONTEND_BASE_URL
    assert profile_b_url == config.DEFAULT_BACKEND_BASE_URL
    assert profile_a_url != profile_b_url
    assert ":11434" in profile_a_url
    assert ":11435" in profile_b_url
    assert ":11436" not in profile_a_url
    assert ":11436" not in profile_b_url


def test_run_ab_comparison_uses_distinct_lane_urls_and_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FRONTEND_MODEL", "frontend-env-24b")
    monkeypatch.setenv("AI_BACKEND_MODEL", "backend-env-30b")
    captured: list[tuple[str, str]] = []

    def fake_generate_response_result(base_url, profile, prompt, timeout_seconds, seed=None):
        captured.append((base_url, str(profile["model"])))
        return {
            "response_text": f"{profile['model']}::{seed}",
            "metrics": {
                "time_to_first_token_estimate_seconds": 0.4,
                "output_tokens_per_second": 80.0,
                "prompt_tokens_per_second": 300.0,
                "end_to_end_tokens_per_second": 70.0,
            },
            "raw_body": {},
        }

    monkeypatch.setattr("app.evaluation.ab_compare.generate_response_result", fake_generate_response_result)
    monkeypatch.setattr("app.evaluation.ab_compare.get_hal_operating_picture", lambda: None)

    run_ab_comparison(
        prompts=[{"id": "plain", "prompt": "Summarize collections risk."}],
        config=AB_CONFIG,
        base_url="unused",
        timeout_seconds=5,
        profile_a_alias="chat",
        profile_b_alias="chat_second_opinion",
        profile_a_base_url=FRONTEND_LANE_URL,
        profile_b_base_url=BACKEND_LANE_URL,
    )

    assert captured == [
        (FRONTEND_LANE_URL, "frontend-env-24b"),
        (BACKEND_LANE_URL, "backend-env-30b"),
    ]
    assert captured[0][0] != captured[1][0]


def test_ab_eval_defaults_do_not_use_evaluator_lane() -> None:
    module = _load_ab_eval_module()
    lane_a, lane_b = module._resolve_lane_targets(AB_CONFIG, "chat", "coder", "")

    evaluator_url = config.get_evaluator_base_url()
    for lane in (lane_a, lane_b):
        assert lane["base_url"] != evaluator_url
        assert ":11436" not in str(lane["base_url"])
        assert lane["model"] != "qwen3:235b"
        assert lane["profile"]["model"] != "qwen3:235b"


def test_ab_eval_script_documents_lane_specific_defaults() -> None:
    script_text = AB_EVAL_SCRIPT.read_text(encoding="utf-8")
    assert "lane URL" in script_text
    assert "resolve_ab_eval_lane" in script_text
    assert "qwen3:235b" not in script_text
