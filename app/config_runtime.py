from __future__ import annotations

from pathlib import Path


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