from __future__ import annotations

from pathlib import Path

LOCAL_APP_ENVIRONMENTS = frozenset({"development", "dev", "test", "testing", "local"})
PRODUCTION_APP_ENVIRONMENTS = frozenset({"production", "prod", "staging"})


def get_app_environment() -> str:
    import os

    return str(os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "").strip().lower()


def is_local_app_environment() -> bool:
    return get_app_environment() in LOCAL_APP_ENVIRONMENTS


def is_production_like_app_environment() -> bool:
    environment = get_app_environment()
    if not environment:
        return True
    if environment in LOCAL_APP_ENVIRONMENTS:
        return False
    return True


def get_env_setting(name: str, default: str = "") -> str:
    runtime_value = __import__("os").getenv(name)
    if runtime_value is not None and runtime_value != "":
        return runtime_value

    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == name:
                return value.strip().strip('"').strip("'")

    return default