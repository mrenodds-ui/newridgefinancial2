from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.config_runtime import get_env_setting
from app.evaluation.client import check_ollama_available, resolve_profile

LOCAL_MODEL_PROFILE_CONFIG_PATH = Path(__file__).resolve().parents[1] / "evals" / "local_model_profiles.json"

FRONTEND_PROFILE_ALIASES = frozenset({"chat"})
BACKEND_PROFILE_ALIASES = frozenset({"chat_second_opinion", "coder"})
FAST_REVIEW_PROFILE_ALIASES = frozenset({"fast_review"})
FAST_OFFICE_PROFILE_ALIASES = frozenset({"chat_fast"})

DEFAULT_FRONTEND_MODEL = "queen3:14b"
DEFAULT_BACKEND_MODEL = "queen3:14b"
DEFAULT_FAST_REVIEW_MODEL = "qwen3-coder:30b"
DEFAULT_HAL_FAST_MODEL = "queen3:14b"
DEFAULT_FRONTEND_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:11435"
DEFAULT_EVALUATOR_BASE_URL = "http://127.0.0.1:11436"
DEFAULT_FAST_REVIEW_BASE_URL = "http://127.0.0.1:11437"

LITELLM_FRONTEND_ALIASES = frozenset({"hal-chat-balanced", "hal-vision"})
LITELLM_BACKEND_ALIASES = frozenset({"hal-coding", "hal-analysis", "hal-second-opinion"})
OLLAMA_FRONTEND_BASE_URL_ENV = "OLLAMA_FRONTEND_BASE_URL"
OLLAMA_BACKEND_BASE_URL_ENV = "OLLAMA_BACKEND_BASE_URL"
OLLAMA_LEGACY_FRONTEND_BASE_URL_ENV = "OLLAMA_BASE_URL"
OLLAMA_FRONTEND_MODEL_ENV = "OLLAMA_FRONTEND_MODEL"
OLLAMA_BACKEND_MODEL_ENV = "OLLAMA_BACKEND_MODEL"
OLLAMA_FAST_REVIEW_BASE_URL_ENV = "OLLAMA_FAST_REVIEW_BASE_URL"
OLLAMA_FAST_REVIEW_MODEL_ENV = "OLLAMA_FAST_REVIEW_MODEL"
DEFAULT_FRONTEND_QUANT = "Q4_K_M"
DEFAULT_BACKEND_QUANT = "Q4_K_M"
DEFAULT_CONTEXT_SIZE = 3072
DEFAULT_LITELLM_PROXY_BASE_URL = "http://127.0.0.1:4000"


class LocalAIConfigError(RuntimeError):
    """Raised when local AI configuration is missing or invalid."""


def _env(name: str, default: str = "") -> str:
    return get_env_setting(name, default)


def get_ai_runtime() -> str:
    runtime = _env("AI_RUNTIME", "ollama").strip().lower()
    if runtime in {"", "ollama"}:
        return "ollama"
    return runtime


def get_ai_gpu_backend() -> str:
    return _env("AI_GPU_BACKEND", "vulkan").strip().lower() or "vulkan"


def _strip_openai_suffix(url: str) -> str:
    normalized = url.strip().rstrip("/")
    if normalized.endswith("/v1"):
        return normalized[:-3]
    return normalized


def get_frontend_base_url() -> str:
    explicit = _env("AI_FRONTEND_BASE_URL") or _env(OLLAMA_FRONTEND_BASE_URL_ENV)
    if explicit:
        return _strip_openai_suffix(explicit)
    legacy = _env(OLLAMA_LEGACY_FRONTEND_BASE_URL_ENV)
    if legacy:
        return _strip_openai_suffix(legacy)
    return DEFAULT_FRONTEND_BASE_URL


def get_backend_base_url() -> str:
    explicit = _env("AI_BACKEND_BASE_URL") or _env(OLLAMA_BACKEND_BASE_URL_ENV)
    if explicit:
        return _strip_openai_suffix(explicit)
    return DEFAULT_BACKEND_BASE_URL


def get_fast_review_base_url() -> str:
    explicit = _env("AI_FAST_REVIEW_BASE_URL") or _env(OLLAMA_FAST_REVIEW_BASE_URL_ENV)
    if explicit:
        return _strip_openai_suffix(explicit)
    return DEFAULT_FAST_REVIEW_BASE_URL


def get_evaluator_base_url() -> str:
    explicit = _env("AI_EVALUATOR_BASE_URL") or _env("OLLAMA_EVALUATOR_BASE_URL")
    if explicit:
        return _strip_openai_suffix(explicit)
    return DEFAULT_EVALUATOR_BASE_URL


def get_litellm_proxy_base_url() -> str:
    explicit = _env("LITELLM_PROXY_BASE_URL")
    if explicit.strip():
        return explicit.strip().rstrip("/")
    return DEFAULT_LITELLM_PROXY_BASE_URL


def litellm_lane_for_alias(alias: str) -> str:
    if alias in LITELLM_BACKEND_ALIASES:
        return "backend"
    if alias in LITELLM_FRONTEND_ALIASES:
        return "frontend"
    raise LocalAIConfigError(f"Unknown LiteLLM alias: {alias}")


def litellm_api_base_env_for_alias(alias: str) -> str:
    if litellm_lane_for_alias(alias) == "backend":
        return OLLAMA_BACKEND_BASE_URL_ENV
    return OLLAMA_FRONTEND_BASE_URL_ENV


def resolve_litellm_api_base_url(alias: str) -> str:
    if litellm_lane_for_alias(alias) == "backend":
        return get_backend_base_url()
    return get_frontend_base_url()


def build_litellm_environment_variables(*, proxy_base_url: str = "") -> dict[str, str]:
    frontend_base_url = get_frontend_base_url()
    backend_base_url = get_backend_base_url()
    environment_variables = {
        OLLAMA_FRONTEND_BASE_URL_ENV: frontend_base_url,
        OLLAMA_LEGACY_FRONTEND_BASE_URL_ENV: frontend_base_url,
        OLLAMA_BACKEND_BASE_URL_ENV: backend_base_url,
    }
    if proxy_base_url.strip():
        environment_variables["LITELLM_PROXY_BASE_URL"] = proxy_base_url.strip().rstrip("/")
    return environment_variables


def get_frontend_model_name() -> str:
    explicit = _env("AI_FRONTEND_MODEL") or _env(OLLAMA_FRONTEND_MODEL_ENV)
    if explicit.strip():
        return explicit.strip()
    return DEFAULT_FRONTEND_MODEL


def get_backend_model_name() -> str:
    explicit = _env("AI_BACKEND_MODEL") or _env(OLLAMA_BACKEND_MODEL_ENV)
    if explicit.strip():
        return explicit.strip()
    return DEFAULT_BACKEND_MODEL


def get_fast_review_model_name() -> str:
    explicit = _env("AI_FAST_REVIEW_MODEL") or _env(OLLAMA_FAST_REVIEW_MODEL_ENV)
    if explicit.strip():
        return explicit.strip()
    return DEFAULT_FAST_REVIEW_MODEL


def get_hal_fast_model_name() -> str:
    explicit = _env("HAL_FAST_MODEL_NAME")
    if explicit.strip():
        return explicit.strip()
    return DEFAULT_HAL_FAST_MODEL


def get_hal_fast_model_base_url() -> str:
    explicit = _env("HAL_FAST_MODEL_BASE_URL")
    if explicit.strip():
        return _strip_openai_suffix(explicit)
    return get_frontend_base_url()


def hal_fast_model_enabled() -> bool:
    return _env("HAL_ENABLE_FAST_MODEL", "1").strip().lower() not in {"0", "false", "no", "off"}


def get_hal_fast_model_timeout_seconds() -> int:
    return _parse_positive_int(_env("HAL_FAST_MODEL_TIMEOUT_SECONDS", "10"), 10)


def get_hal_main_model_timeout_seconds() -> int:
    return _parse_positive_int(_env("HAL_MAIN_MODEL_TIMEOUT_SECONDS", "15"), 15)


def get_frontend_model_path() -> str:
    return _env("AI_FRONTEND_MODEL_PATH")


def get_backend_model_path() -> str:
    return _env("AI_BACKEND_MODEL_PATH")


def get_frontend_context_size() -> int:
    return _parse_positive_int(
        _env("AI_FRONTEND_CONTEXT_SIZE") or _env("AI_CONTEXT_SIZE"),
        DEFAULT_CONTEXT_SIZE,
    )


def get_backend_context_size() -> int:
    return _parse_positive_int(
        _env("AI_BACKEND_CONTEXT_SIZE") or _env("AI_CONTEXT_SIZE"),
        DEFAULT_CONTEXT_SIZE,
    )


def get_frontend_quantization() -> str:
    return _env("AI_FRONTEND_QUANT", DEFAULT_FRONTEND_QUANT)


def get_backend_quantization() -> str:
    return _env("AI_BACKEND_QUANT", DEFAULT_BACKEND_QUANT)


def is_fast_review_profile_alias(alias: str) -> bool:
    return alias in FAST_REVIEW_PROFILE_ALIASES


def is_fast_office_profile_alias(alias: str) -> bool:
    return alias in FAST_OFFICE_PROFILE_ALIASES


def profile_lane(alias: str) -> str:
    if is_fast_review_profile_alias(alias):
        return "fast_review"
    if is_fast_office_profile_alias(alias):
        return "fast_office"
    if alias in BACKEND_PROFILE_ALIASES:
        return "backend"
    if alias in FRONTEND_PROFILE_ALIASES:
        return "frontend"
    return "frontend"


def get_base_url_for_profile_alias(alias: str) -> str:
    if is_fast_office_profile_alias(alias):
        return get_hal_fast_model_base_url()
    if is_fast_review_profile_alias(alias):
        return get_fast_review_base_url()
    if profile_lane(alias) == "backend":
        return get_backend_base_url()
    return get_frontend_base_url()


def get_model_for_profile_alias(alias: str) -> str:
    if is_fast_office_profile_alias(alias):
        return get_hal_fast_model_name()
    if is_fast_review_profile_alias(alias):
        return get_fast_review_model_name()
    if profile_lane(alias) == "backend":
        return get_backend_model_name()
    return get_frontend_model_name()


def resolve_profile_base_url(alias: str, *, override_base_url: str = "") -> str:
    if override_base_url.strip():
        return _strip_openai_suffix(override_base_url)
    return get_base_url_for_profile_alias(alias)


def _parse_positive_int(raw_value: str, default: int) -> int:
    if not raw_value.strip():
        return default
    try:
        parsed = int(raw_value.strip())
    except ValueError as exc:
        raise LocalAIConfigError(f"Invalid integer AI context setting: {raw_value!r}") from exc
    if parsed < 1:
        raise LocalAIConfigError(f"AI context size must be positive, got {parsed}.")
    return parsed


def _apply_gpu_layer_override(profile: dict[str, Any], lane: str) -> dict[str, Any]:
    merged = dict(profile)
    layers_raw = _env("AI_GPU_LAYERS")
    if not layers_raw or layers_raw.strip().lower() == "auto":
        return merged
    try:
        if layers_raw.strip().lower() == "cpu":
            merged["num_gpu"] = 0
        else:
            merged["num_gpu"] = int(layers_raw.strip())
    except ValueError as exc:
        raise LocalAIConfigError(f"AI_GPU_LAYERS must be auto, cpu, or an integer. Got {layers_raw!r}.") from exc
    if lane == "backend" and layers_raw.strip().lower() == "auto" and merged.get("num_gpu") is None:
        merged["num_gpu"] = 0
    return merged


def apply_lane_env_overrides(profile: dict[str, Any], alias: str) -> dict[str, Any]:
    lane = profile_lane(alias)
    merged = dict(profile)
    if is_fast_office_profile_alias(alias):
        model_name = get_hal_fast_model_name()
        context_size = min(get_frontend_context_size(), 2048)
        quant = get_frontend_quantization()
    elif is_fast_review_profile_alias(alias):
        model_name = get_fast_review_model_name()
        context_size = get_backend_context_size()
        quant = get_backend_quantization()
    elif lane == "backend":
        model_name = get_backend_model_name()
        context_size = get_backend_context_size()
        quant = get_backend_quantization()
    else:
        model_name = get_frontend_model_name()
        context_size = get_frontend_context_size()
        quant = get_frontend_quantization()

    if model_name:
        merged["model"] = model_name
    merged["num_ctx"] = context_size
    merged["gguf_quant"] = quant
    return _apply_gpu_layer_override(merged, lane if lane != "fast_review" else "backend")


def resolve_lane_profile(config: dict[str, Any], alias: str) -> dict[str, Any]:
    profile = resolve_profile(config, alias)
    return apply_lane_env_overrides(profile, alias)


def resolve_ab_eval_lane(
    config: dict[str, Any],
    alias: str,
    *,
    override_base_url: str = "",
) -> dict[str, object]:
    return {
        "alias": alias,
        "lane": profile_lane(alias),
        "base_url": resolve_profile_base_url(alias, override_base_url=override_base_url),
        "model": get_model_for_profile_alias(alias),
        "profile": resolve_lane_profile(config, alias),
    }


def load_local_model_profile_config() -> dict[str, Any]:
    if not LOCAL_MODEL_PROFILE_CONFIG_PATH.exists():
        raise LocalAIConfigError(
            f"Local model profile config is missing at {LOCAL_MODEL_PROFILE_CONFIG_PATH}. "
            "Restore evals/local_model_profiles.json or set cloud/OpenAI credentials instead."
        )
    import json

    payload = json.loads(LOCAL_MODEL_PROFILE_CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LocalAIConfigError("evals/local_model_profiles.json must contain a JSON object.")
    return payload


def validate_local_model_paths(*, runtime: str | None = None) -> None:
    active_runtime = (runtime or get_ai_runtime()).strip().lower()
    if active_runtime not in {"llama_cpp", "llama-cpp"}:
        return

    missing: list[str] = []
    frontend_path = get_frontend_model_path()
    backend_path = get_backend_model_path()
    if not frontend_path:
        missing.append("AI_FRONTEND_MODEL_PATH")
    elif not Path(frontend_path).is_file():
        missing.append(f"AI_FRONTEND_MODEL_PATH ({frontend_path})")
    if not backend_path:
        missing.append("AI_BACKEND_MODEL_PATH")
    elif not Path(backend_path).is_file():
        missing.append(f"AI_BACKEND_MODEL_PATH ({backend_path})")

    if missing:
        raise LocalAIConfigError(
            "Local llama.cpp runtime requires quantized GGUF model files. Missing or not found: "
            + ", ".join(missing)
            + ". Run scripts/quantize_frontend_24b.sh and scripts/quantize_backend_30b.sh first."
        )


def check_lane_runtime_available(alias: str, *, timeout_seconds: int = 5) -> tuple[bool, str | None]:
    validate_local_model_paths()
    base_url = get_base_url_for_profile_alias(alias)
    if _is_openai_compatible_runtime(base_url):
        return _check_openai_compatible_runtime(base_url, timeout_seconds=timeout_seconds)
    return check_ollama_available(base_url, timeout_seconds=timeout_seconds)


def _is_openai_compatible_runtime(base_url: str) -> bool:
    explicit = _env("AI_OPENAI_COMPATIBLE", "").strip().lower()
    if explicit in {"1", "true", "yes", "on"}:
        return True
    return bool(_env("AI_FRONTEND_BASE_URL")) or bool(_env("AI_BACKEND_BASE_URL"))


def _check_openai_compatible_runtime(base_url: str, *, timeout_seconds: int) -> tuple[bool, str | None]:
    import requests

    normalized = base_url.rstrip("/")
    models_url = f"{normalized}/v1/models" if not normalized.endswith("/v1") else f"{normalized}/models"
    try:
        response = requests.get(models_url, timeout=timeout_seconds)
        response.raise_for_status()
    except requests.RequestException as exc:
        return False, str(exc)
    return True, None


def get_model_routing_snapshot() -> dict[str, object]:
    return {
        "runtime": get_ai_runtime(),
        "gpu_backend": get_ai_gpu_backend(),
        "frontend": {
            "base_url": get_frontend_base_url(),
            "model": get_frontend_model_name(),
            "context_size": get_frontend_context_size(),
            "quantization": get_frontend_quantization(),
            "model_path": get_frontend_model_path() or None,
            "profile_aliases": sorted(FRONTEND_PROFILE_ALIASES),
        },
        "backend": {
            "base_url": get_backend_base_url(),
            "model": get_backend_model_name(),
            "context_size": get_backend_context_size(),
            "quantization": get_backend_quantization(),
            "model_path": get_backend_model_path() or None,
            "profile_aliases": sorted(BACKEND_PROFILE_ALIASES),
        },
        "fast_review": {
            "experimental": True,
            "opt_in": True,
            "base_url": get_fast_review_base_url(),
            "model": get_fast_review_model_name(),
            "context_size": get_backend_context_size(),
            "quantization": get_backend_quantization(),
            "profile_aliases": sorted(FAST_REVIEW_PROFILE_ALIASES),
        },
        "fast_office": {
            "enabled": hal_fast_model_enabled(),
            "base_url": get_hal_fast_model_base_url(),
            "model": get_hal_fast_model_name(),
            "timeout_seconds": get_hal_fast_model_timeout_seconds(),
            "profile_aliases": sorted(FAST_OFFICE_PROFILE_ALIASES),
        },
        "profile_base_urls": {
            alias: get_base_url_for_profile_alias(alias)
            for alias in sorted(FRONTEND_PROFILE_ALIASES | BACKEND_PROFILE_ALIASES | FAST_OFFICE_PROFILE_ALIASES)
        },
        "optional_profile_base_urls": {
            alias: get_base_url_for_profile_alias(alias)
            for alias in sorted(FAST_REVIEW_PROFILE_ALIASES)
        },
    }


def require_lane_runtime(alias: str, *, purpose: str) -> str:
    available, error_message = check_lane_runtime_available(alias)
    if available:
        return get_base_url_for_profile_alias(alias)
    lane = profile_lane(alias)
    model_name = get_backend_model_name() if lane == "backend" else get_frontend_model_name()
    base_url = get_base_url_for_profile_alias(alias)
    raise LocalAIConfigError(
        f"Local AI runtime unavailable for {purpose}. "
        f"Lane={lane}, model={model_name}, base_url={base_url}. "
        f"{error_message or 'Start the model server or configure cloud/OpenAI credentials.'}"
    )
