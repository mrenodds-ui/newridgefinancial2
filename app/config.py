from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class AppSettings:
    auth_users_json: str
    auth_session_secret: str
    hal_browser_dev_auth: bool
    ollama_chat_url: str
    ollama_model: str
    ollama_timeout_seconds: float
    ollama_num_predict: int
    ollama_num_ctx: int
    ollama_think: bool
    cors_origins: tuple[str, ...]


def _parse_cors_origins(cors_raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in cors_raw.split(",") if part.strip())


def runtime_warnings(settings: AppSettings) -> tuple[str, ...]:
    warnings: list[str] = []
    if settings.hal_browser_dev_auth and not settings.auth_session_secret:
        warnings.append(
            "HAL_BROWSER_DEV_AUTH is enabled without APP_AUTH_SESSION_SECRET. "
            "Session signing will fall back to auth-user JSON and can rotate when that config changes."
        )
    return tuple(warnings)


@lru_cache(maxsize=1)
def load_settings() -> AppSettings:
    cors_raw = os.environ.get("HAL_BROWSER_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
    return AppSettings(
        auth_users_json=os.environ.get("APP_AUTH_USERS_JSON", "[]"),
        auth_session_secret=os.environ.get("APP_AUTH_SESSION_SECRET", ""),
        hal_browser_dev_auth=_env_bool("HAL_BROWSER_DEV_AUTH", False),
        ollama_chat_url=os.environ.get("HAL_OLLAMA_CHAT_URL", "http://127.0.0.1:11434/api/chat"),
        ollama_model=os.environ.get("HAL_OLLAMA_MODEL", "hal-chat:8b"),
        ollama_timeout_seconds=float(os.environ.get("HAL_OLLAMA_TIMEOUT_SECONDS", "90")),
        ollama_num_predict=int(os.environ.get("HAL_OLLAMA_NUM_PREDICT", "512")),
        ollama_num_ctx=int(os.environ.get("HAL_OLLAMA_NUM_CTX", "4096")),
        ollama_think=_env_bool("HAL_OLLAMA_THINK", False),
        cors_origins=_parse_cors_origins(cors_raw),
    )


def clear_settings_cache() -> None:
    load_settings.cache_clear()


def default_dev_auth_users_json() -> str:
    return json.dumps(
        [
            {
                "username": "office.manager",
                "display_name": "Office Manager",
                "password": "office-manager",
                "roles": ["dashboard:read", "hal:operator"],
            }
        ]
    )
