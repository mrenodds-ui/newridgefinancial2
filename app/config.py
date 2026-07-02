from __future__ import annotations

import json
import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class AppSettings:
    auth_users_json: str
    hal_browser_dev_auth: bool
    ollama_chat_url: str
    ollama_model: str
    ollama_timeout_seconds: float
    cors_origins: tuple[str, ...]


def load_settings() -> AppSettings:
    cors_raw = os.environ.get("HAL_BROWSER_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
    return AppSettings(
        auth_users_json=os.environ.get("APP_AUTH_USERS_JSON", "[]"),
        hal_browser_dev_auth=_env_bool("HAL_BROWSER_DEV_AUTH", False),
        ollama_chat_url=os.environ.get("HAL_OLLAMA_CHAT_URL", "http://127.0.0.1:11434/api/chat"),
        ollama_model=os.environ.get("HAL_OLLAMA_MODEL", "hal-chat:8b"),
        ollama_timeout_seconds=float(os.environ.get("HAL_OLLAMA_TIMEOUT_SECONDS", "90")),
        cors_origins=tuple(part.strip() for part in cors_raw.split(",") if part.strip()),
    )


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
