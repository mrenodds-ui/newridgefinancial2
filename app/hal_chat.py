from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field

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


class HalPageContext(BaseModel):
    route: str = ""
    page_title: str = Field(default="", alias="pageTitle")
    captured_at: str = Field(default="", alias="capturedAt")

    model_config = {"populate_by_name": True}


class HalChatMessage(BaseModel):
    role: str
    content: str


class HalChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    page_context: HalPageContext | None = Field(default=None, alias="pageContext")
    history: list[HalChatMessage] = Field(default_factory=list, max_length=20)

    model_config = {"populate_by_name": True}


class HalChatResponse(BaseModel):
    message: str
    mode: str
    local_ai_unavailable: str | None = Field(default=None, alias="localAiUnavailable")

    model_config = {"populate_by_name": True}


def _nr2_root() -> Path:
    return Path(__file__).resolve().parents[1] / "NewRidgeFinancial2"


def load_integration_health_text() -> str:
    nr2_root = _nr2_root()
    if str(nr2_root) not in sys.path:
        sys.path.insert(0, str(nr2_root))
    try:
        from integration_health import format_integration_health_text, integration_health_snapshot

        snapshot = integration_health_snapshot(deep_diagnostics=False)
        return format_integration_health_text(snapshot)
    except Exception as exc:
        return f"Integration health unavailable: {exc}"


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
    context_lines = [
        SYSTEM_PROMPT,
        "",
        "Current page context:",
        f"- route: {page_context.route if page_context else '/'}",
        f"- page_title: {page_context.page_title if page_context else ''}",
        f"- captured_at: {page_context.captured_at if page_context else ''}",
        "",
        "Integration health snapshot:",
        integration_health,
    ]
    messages: list[dict[str, str]] = [{"role": "system", "content": "\n".join(context_lines)}]
    for item in history[-8:]:
        role = item.role if item.role in {"user", "assistant"} else "user"
        messages.append({"role": role, "content": item.content[:4000]})
    messages.append({"role": "user", "content": message})
    return messages


def call_ollama(messages: list[dict[str, str]], settings: AppSettings | None = None) -> str:
    settings = settings or load_settings()
    payload: dict[str, Any] = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 420, "num_ctx": 4096},
    }
    with httpx.Client(timeout=settings.ollama_timeout_seconds) as client:
        response = client.post(settings.ollama_chat_url, json=payload)
        response.raise_for_status()
        body = response.json()
    content = body.get("message", {}).get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Ollama returned an empty response")
    return content.strip()


def generate_hal_chat_response(request: HalChatRequest, settings: AppSettings | None = None) -> HalChatResponse:
    settings = settings or load_settings()
    blocked = check_message_policy(request.message)
    if blocked:
        return HalChatResponse(message=blocked, mode="policy-block")

    integration_health = load_integration_health_text()
    messages = build_prompt(
        message=request.message.strip(),
        history=request.history,
        page_context=request.page_context,
        integration_health=integration_health,
    )

    try:
        answer = call_ollama(messages, settings)
        return HalChatResponse(message=answer, mode="local-ollama")
    except Exception as exc:
        return HalChatResponse(
            message=(
                "HAL could not reach the local Ollama chat model right now. "
                f"Details: {exc}. "
                "Integration health and page context were loaded, but no model reply was generated."
            ),
            mode="fallback",
            local_ai_unavailable=str(exc),
        )
