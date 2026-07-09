from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Settings:
    backend: str
    base_url: str
    health_url: str
    models_url: str
    api_key: str
    model_fast: str
    model_heavy: str
    health_timeout: float
    max_tokens: int
    temperature: float
    simple_keywords: tuple[str, ...]
    complex_keywords: tuple[str, ...]
    warmup_prompt: str


def _load_yaml_config() -> dict:
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    if not config_path.exists():
        return {}
    with config_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_settings() -> Settings:
    yaml_cfg = _load_yaml_config()
    backend = os.getenv("LLM_BACKEND", yaml_cfg.get("backend", "ollama")).strip().lower()
    server_cfg = (yaml_cfg.get("server") or {}).get(backend, {})

    base_url = os.getenv("LLM_BASE_URL", server_cfg.get("base_url", "http://127.0.0.1:11434/v1"))
    health_url = server_cfg.get("health_url", base_url.replace("/v1", "/api/version"))
    models_url = server_cfg.get("models_url", base_url.replace("/v1", "/api/tags"))

    models = yaml_cfg.get("models") or {}
    routing = yaml_cfg.get("routing") or {}
    benchmark = yaml_cfg.get("benchmark") or {}

    return Settings(
        backend=backend,
        base_url=base_url.rstrip("/"),
        health_url=health_url,
        models_url=models_url,
        api_key=os.getenv("LLM_API_KEY", "ollama"),
        model_fast=os.getenv("LLM_MODEL_FAST", (models.get("fast") or {}).get("name", "llama3:8b-instruct-fp16")),
        model_heavy=os.getenv("LLM_MODEL_HEAVY", (models.get("heavy") or {}).get("name", "qwen3:30b")),
        health_timeout=float(os.getenv("LLM_HEALTH_TIMEOUT", "5")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "512")),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
        simple_keywords=tuple(routing.get("simple_keywords") or ()),
        complex_keywords=tuple(routing.get("complex_keywords") or ()),
        warmup_prompt=benchmark.get("warmup_prompt", "Reply with the single word: ready"),
    )
