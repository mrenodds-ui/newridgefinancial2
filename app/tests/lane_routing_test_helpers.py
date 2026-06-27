from __future__ import annotations

from typing import Any, Callable

from app import ai_local_config as config

FRONTEND_LANE_URL = "http://127.0.0.1:11434"
BACKEND_LANE_URL = "http://127.0.0.1:11435"
EVALUATOR_LANE_URL = "http://127.0.0.1:11436"
FAST_REVIEW_LANE_URL = "http://127.0.0.1:11437"

FRONTEND_LANE_MODEL = "qwen3:14b"
BACKEND_LANE_MODEL = "qwen3:14b"
EVALUATOR_LANE_MODEL = "qwen3:235b"
FAST_REVIEW_LANE_MODEL = "qwen3-coder:30b"


def lane_from_url(url: str) -> str:
    if ":11436" in url:
        return "evaluator"
    if ":11437" in url:
        return "fast_review"
    if ":11435" in url:
        return "backend"
    if ":11434" in url:
        return "frontend"
    raise AssertionError(f"Unexpected lane URL in test mock: {url}")


def tags_payload_for_lane(lane: str) -> dict[str, object]:
    if lane == "frontend":
        models = [
            {
                "name": FRONTEND_LANE_MODEL,
                "capabilities": ["completion", "tools", "vision"],
                "details": {
                    "family": "qwen3",
                    "parameter_size": "14.8B",
                    "context_length": 40960,
                },
            },
            {
                "name": "gpt-oss:120b",
                "capabilities": ["completion", "tools", "thinking"],
                "details": {
                    "family": "gptoss",
                    "parameter_size": "116.8B",
                    "context_length": 131072,
                },
            },
        ]
    elif lane == "backend":
        models = [
            {
                "name": BACKEND_LANE_MODEL,
                "capabilities": ["completion", "tools", "thinking"],
                "details": {
                    "family": "qwen3",
                    "parameter_size": "14.8B",
                    "context_length": 40960,
                },
            },
        ]
    elif lane == "fast_review":
        models = [
            {
                "name": FAST_REVIEW_LANE_MODEL,
                "capabilities": ["completion", "tools"],
                "details": {
                    "family": "qwen3",
                    "parameter_size": "30.0B",
                    "context_length": 32768,
                },
            },
        ]
    else:
        raise AssertionError(f"Evaluator lane must not be used in normal routing mocks: {lane}")

    return {"models": models}


def make_lane_aware_requests_get(
    fake_response_class: type,
    *,
    backend_unreachable: bool = False,
    proxy_models_payload: dict[str, object] | None = None,
) -> Callable[..., Any]:
    proxy_payload = proxy_models_payload or {
        "data": [
            {"id": "hal-chat-balanced"},
            {"id": "hal-coding"},
            {"id": "hal-analysis"},
            {"id": "hal-second-opinion"},
            {"id": "hal-vision"},
        ]
    }

    def fake_get(url: str, timeout: int = 5, headers: dict[str, str] | None = None) -> Any:
        if url.endswith("/v1/models"):
            return fake_response_class(proxy_payload)

        lane = lane_from_url(url)
        if lane == "evaluator":
            raise AssertionError("Normal routing tests must not call evaluator lane :11436")

        if "/api/tags" in url:
            if lane == "backend" and backend_unreachable:
                return fake_response_class({"models": []}, status_code=503)
            return fake_response_class(tags_payload_for_lane(lane))

        raise AssertionError(f"Unexpected URL in lane-aware mock: {url}")

    return fake_get


def make_require_lane_runtime_mock(*, expected_alias: str) -> Callable[..., str]:
    def fake_require_lane_runtime(alias: str, *, purpose: str) -> str:
        assert alias == expected_alias, (
            f"Expected require_lane_runtime alias {expected_alias!r}, got {alias!r} ({purpose})"
        )
        resolved = config.resolve_profile_base_url(alias)
        if alias in config.BACKEND_PROFILE_ALIASES:
            assert ":11435" in resolved, f"Backend alias {alias} must resolve to :11435, got {resolved}"
            assert ":11434" not in resolved, f"Backend alias {alias} must not resolve to frontend :11434"
            assert ":11437" not in resolved, f"Backend alias {alias} must not resolve to fast review :11437"
        elif alias in config.FRONTEND_PROFILE_ALIASES:
            assert ":11434" in resolved, f"Frontend alias {alias} must resolve to :11434, got {resolved}"
            assert ":11435" not in resolved, f"Frontend alias {alias} must not resolve to backend :11435"
            assert ":11437" not in resolved, f"Frontend alias {alias} must not resolve to fast review :11437"
        elif config.is_fast_review_profile_alias(alias):
            assert ":11437" in resolved, f"Fast review alias {alias} must resolve to :11437, got {resolved}"
        assert ":11436" not in resolved, f"Normal profile {alias} must not resolve to evaluator :11436"
        return resolved

    return fake_require_lane_runtime


def make_ollama_runtime_status_mock(
    *,
    frontend_reachable: bool = True,
    backend_reachable: bool = True,
) -> tuple[Callable[..., dict[str, object]], list[str]]:
    calls: list[str] = []

    def fake_runtime_status(base_url: str, timeout_seconds: int = 5) -> dict[str, object]:
        calls.append(base_url)
        lane = lane_from_url(base_url)
        if lane == "evaluator":
            raise AssertionError("HAL status must not probe evaluator lane :11436")

        reachable = frontend_reachable if lane == "frontend" else backend_reachable
        models = [FRONTEND_LANE_MODEL] if lane == "frontend" else [BACKEND_LANE_MODEL]
        if lane == "frontend" and frontend_reachable:
            models.append(BACKEND_LANE_MODEL)
        return {
            "base_url": base_url,
            "installed": bool(models) and reachable,
            "running": reachable,
            "api_reachable": reachable,
            "installed_models": models if reachable else [],
            "model_count": len(models) if reachable else 0,
            "error": None if reachable else "connection refused",
        }

    return fake_runtime_status, calls
