from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module
from time import monotonic
import re
import sys
from pathlib import Path
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field, field_validator

from .config import AppSettings, load_settings

BLOCKED_ACTION_RE = re.compile(
    r"\b(submit|send|email|fax|upload|writeback|write back|dispatch|wire)\b",
    re.IGNORECASE,
)

SYSTEM_PROMPT = """You are HAL, the internal office assistant for New Ridge Family Financial.

Safety boundaries (always enforce):
- Read / draft / local-only by default
- No SoftDent writeback
- No claim submission
- No faxing
- No emailing
- No uploading
- No external action

Use the page context and integration health snapshot when helpful.
Do not invent patient PHI or specific financial numbers unless they appear in the provided context.
Be concise, professional, and practical for office-manager workflows."""

MAX_HISTORY_ITEMS = 20
MAX_PROMPT_HISTORY_ITEMS = 8
MAX_PROMPT_CONTENT_CHARS = 4000
INTEGRATION_HEALTH_CACHE_SECONDS = 15.0


class HalPageContext(BaseModel):
    route: str = ""
    page_title: str = Field(default="", alias="pageTitle")
    captured_at: str = Field(default="", alias="capturedAt")

    model_config = {"populate_by_name": True}


class HalChatMessage(BaseModel):
    role: str
    content: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Message content cannot be empty")
        return normalized


class HalChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    page_context: HalPageContext | None = Field(default=None, alias="pageContext")
    history: list[HalChatMessage] = Field(default_factory=list, max_length=MAX_HISTORY_ITEMS)

    model_config = {"populate_by_name": True}

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Message cannot be empty")
        return normalized


class HalChatResponse(BaseModel):
    message: str
    mode: str
    local_ai_unavailable: str | None = Field(default=None, alias="localAiUnavailable")

    model_config = {"populate_by_name": True}


class IntegrationHealthProvider(Protocol):
    def __call__(self) -> str: ...


@dataclass(slots=True)
class IntegrationHealthCache:
    value: str = ""
    expires_at: float = 0.0


_integration_health_cache = IntegrationHealthCache()


def _nr2_root() -> Path:
    return Path(__file__).resolve().parents[1] / "NewRidgeFinancial2"


def _ensure_nr2_import_path() -> None:
    nr2_root = _nr2_root()

    nr2_root_str = str(nr2_root)
    if nr2_root_str not in sys.path:
        sys.path.insert(0, nr2_root_str)


@lru_cache(maxsize=1)
def _load_integration_health_provider() -> IntegrationHealthProvider:
    _ensure_nr2_import_path()
    integration_health = import_module("integration_health")

    formatter = getattr(integration_health, "format_integration_health_text")
    snapshot_loader = getattr(integration_health, "integration_health_snapshot")

    def provide() -> str:
        snapshot = snapshot_loader(deep_diagnostics=False)
        return formatter(snapshot)

    return provide


def _read_integration_health_cache(now: float | None = None) -> str | None:
    current_time = monotonic() if now is None else now
    if _integration_health_cache.expires_at <= current_time:
        return None
    return _integration_health_cache.value


def _write_integration_health_cache(value: str, now: float | None = None) -> None:
    current_time = monotonic() if now is None else now
    _integration_health_cache.value = value
    _integration_health_cache.expires_at = current_time + INTEGRATION_HEALTH_CACHE_SECONDS


def load_integration_health_text() -> str:
    cached = _read_integration_health_cache()
    if cached is not None:
        return cached

    try:
        value = _load_integration_health_provider()()
    except Exception as exc:
        value = f"Integration health unavailable: {exc}"

    _write_integration_health_cache(value)
    return value


def check_message_policy(message: str) -> str | None:
    if BLOCKED_ACTION_RE.search(message):
        return (
            "That request looks like an external action, so HAL stops at the safety boundary. "
            "I can explain status, draft internal notes, or summarize local dashboards — "
            "but a person must perform external steps outside HAL."
        )
    return None


def build_prompt(
    *,
    message: str,
    history: list[HalChatMessage],
    page_context: HalPageContext | None,
    integration_health: str,
) -> list[dict[str, str]]:
    current_page_context = page_context or HalPageContext()
    context_lines = [
        SYSTEM_PROMPT,
        "",
        "Current page context:",
        f"- route: {current_page_context.route or '/'}",
        f"- page_title: {current_page_context.page_title}",
        f"- captured_at: {current_page_context.captured_at}",
        "",
        "Integration health snapshot:",
        integration_health,
    ]
    messages: list[dict[str, str]] = [{"role": "system", "content": "\n".join(context_lines)}]
    for item in history[-MAX_PROMPT_HISTORY_ITEMS:]:
        role = item.role if item.role in {"user", "assistant"} else "user"
        messages.append({"role": role, "content": item.content[:MAX_PROMPT_CONTENT_CHARS]})
    messages.append({"role": "user", "content": message})
    return messages


def extract_ollama_text(body: dict[str, Any]) -> str:
    message = body.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("Ollama returned an unexpected response shape")

    content = str(message.get("content") or "").strip()
    if content:
        return content

    done_reason = str(body.get("done_reason") or "")
    if done_reason == "length":
        raise RuntimeError(
            "Ollama hit the token limit before producing a final answer. "
            "Increase HAL_OLLAMA_NUM_PREDICT or shorten the prompt."
        )

    raise RuntimeError("Ollama returned an empty response")


def _build_ollama_payload(messages: list[dict[str, str]], settings: AppSettings) -> dict[str, Any]:
    return {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
        "think": settings.ollama_think,
        "options": {
            "temperature": 0.2,
            "num_predict": settings.ollama_num_predict,
            "num_ctx": settings.ollama_num_ctx,
        },
    }


async def call_ollama(messages: list[dict[str, str]], settings: AppSettings | None = None) -> str:
    settings = settings or load_settings()
    payload = _build_ollama_payload(messages, settings)
    async with httpx.AsyncClient(timeout=settings.ollama_timeout_seconds) as client:
        response = await client.post(settings.ollama_chat_url, json=payload)
        response.raise_for_status()
        body = response.json()
    return extract_ollama_text(body)


def build_fallback_message(exc: Exception, integration_health: str) -> str:
    health_excerpt = integration_health.strip()
    if len(health_excerpt) > 1800:
        health_excerpt = health_excerpt[:1800].rstrip() + "…"
    return (
        "HAL could not produce a local model reply right now. "
        f"Details: {exc}\n\n"
        "Here is the latest local integration snapshot I can share safely:\n\n"
        f"{health_excerpt}"
    )


async def generate_hal_chat_response(request: HalChatRequest, settings: AppSettings | None = None) -> HalChatResponse:
    settings = settings or load_settings()
    blocked = check_message_policy(request.message)
    if blocked:
        return HalChatResponse(message=blocked, mode="policy-block")

    integration_health = await asyncio.to_thread(load_integration_health_text)
    messages = build_prompt(
        message=request.message,
        history=request.history,
        page_context=request.page_context,
        integration_health=integration_health,
    )

    try:
        answer = await call_ollama(messages, settings)
        return HalChatResponse(message=answer, mode="local-ollama")
    except Exception as exc:
        return HalChatResponse(
            message=build_fallback_message(exc, integration_health),
            mode="fallback",
            local_ai_unavailable=str(exc),
        )
