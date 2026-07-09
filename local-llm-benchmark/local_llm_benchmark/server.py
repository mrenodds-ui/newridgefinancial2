from __future__ import annotations

from dataclasses import dataclass

import httpx

from .config import Settings


class ServerUnavailableError(RuntimeError):
    """Raised when the local inference server is not reachable or not ready."""


@dataclass(frozen=True)
class ServerStatus:
    backend: str
    health_url: str
    ok: bool
    version: str | None
    installed_models: tuple[str, ...]


def _extract_model_names(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return []
    models = payload.get("models")
    if not isinstance(models, list):
        return []
    names: list[str] = []
    for item in models:
        if isinstance(item, dict):
            name = item.get("name") or item.get("model")
            if isinstance(name, str) and name:
                names.append(name)
        elif isinstance(item, str):
            names.append(item)
    return names


def check_server(settings: Settings) -> ServerStatus:
    timeout = settings.health_timeout
    version: str | None = None
    installed: list[str] = []

    try:
        with httpx.Client(timeout=timeout) as client:
            health = client.get(settings.health_url)
            health.raise_for_status()
            if settings.backend == "ollama":
                payload = health.json()
                if isinstance(payload, dict):
                    version = str(payload.get("version") or "")
            else:
                version = "ok"

            models_resp = client.get(settings.models_url)
            if models_resp.status_code == 200:
                installed = _extract_model_names(models_resp.json())
    except httpx.HTTPError as exc:
        raise ServerUnavailableError(
            f"Local {settings.backend} server is not reachable at {settings.health_url}. "
            f"Start the server and verify the port. Details: {exc}"
        ) from exc

    return ServerStatus(
        backend=settings.backend,
        health_url=settings.health_url,
        ok=True,
        version=version,
        installed_models=tuple(installed),
    )


def ensure_server_ready(settings: Settings, required_models: list[str] | None = None) -> ServerStatus:
    status = check_server(settings)
    if required_models:
        missing = [model for model in required_models if not _model_installed(model, status.installed_models)]
        if missing:
            raise ServerUnavailableError(
                "Server is up but required model(s) are missing: "
                + ", ".join(missing)
                + ". Pull or register them, then retry."
            )
    return status


def _model_installed(target: str, installed: tuple[str, ...]) -> bool:
    target_base = target.split(":")[0]
    for name in installed:
        if name == target or name.startswith(f"{target_base}:"):
            return True
    return False
