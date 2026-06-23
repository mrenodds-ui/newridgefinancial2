from __future__ import annotations

import os
import time
import uuid
from typing import Any

import requests
from fastapi import FastAPI, HTTPException, Request


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_MODEL = os.getenv("GPT_OSS_PROXY_MODEL", "gpt-oss:120b")
PROXY_PORT = int(os.getenv("GPT_OSS_PROXY_PORT", "4010"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("GPT_OSS_PROXY_TIMEOUT_SECONDS", "900"))
MIN_NUM_PREDICT = int(os.getenv("GPT_OSS_PROXY_MIN_NUM_PREDICT", "128"))
HIDDEN_HEADROOM = int(os.getenv("GPT_OSS_PROXY_HIDDEN_HEADROOM", "256"))
HEADROOM_MULTIPLIER = int(os.getenv("GPT_OSS_PROXY_HEADROOM_MULTIPLIER", "2"))
MAX_NUM_PREDICT = int(os.getenv("GPT_OSS_PROXY_MAX_NUM_PREDICT", "1024"))
KEEP_ALIVE = os.getenv("GPT_OSS_PROXY_KEEP_ALIVE", "30m")


app = FastAPI(title="gpt-oss clean proxy")


def _build_final_only_retry_prompt(prompt: str) -> str:
    return (
        f"{prompt}\n\n"
        "IMPORTANT: Return only the final answer. Do not include hidden reasoning, scratchpad, or planning. "
        "If you started internal reasoning, suppress it and answer directly in the requested format."
    )


def _strip_think_tags(text: str) -> str:
    lowered = text.lower()
    if "<think" not in lowered:
        return text.strip()
    output: list[str] = []
    remaining = text
    while remaining:
        start = remaining.lower().find("<think")
        if start == -1:
            output.append(remaining)
            break
        output.append(remaining[:start])
        end = remaining.lower().find("</think>", start)
        if end == -1:
            break
        remaining = remaining[end + len("</think>"):]
    return "".join(output).strip()


def _clean_response_text(body: dict[str, Any]) -> str:
    return _strip_think_tags(str(body.get("response") or "")).strip()


def _thinking_text(body: dict[str, Any]) -> str:
    return str(body.get("thinking") or body.get("reasoning") or "").strip()


def _requested_num_predict(payload: dict[str, Any]) -> int:
    options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    if options.get("num_predict") is not None:
        return max(1, int(options["num_predict"]))
    if payload.get("max_tokens") is not None:
        return max(1, int(payload["max_tokens"]))
    return 512


def _internal_num_predict(requested: int, *, retry: bool) -> int:
    baseline = max(MIN_NUM_PREDICT, requested + HIDDEN_HEADROOM, requested * HEADROOM_MULTIPLIER)
    if retry:
        baseline = max(baseline, requested + (HIDDEN_HEADROOM * 2), requested * (HEADROOM_MULTIPLIER + 1))
    return min(MAX_NUM_PREDICT, baseline)


def _should_retry(body: dict[str, Any]) -> bool:
    if _clean_response_text(body):
        return False
    if _thinking_text(body):
        return True
    return str(body.get("done_reason") or "") == "length"


def _call_ollama_generate(payload: dict[str, Any], *, retry: bool) -> dict[str, Any]:
    requested_predict = _requested_num_predict(payload)
    options = dict(payload.get("options") or {})
    options["num_predict"] = _internal_num_predict(requested_predict, retry=retry)

    upstream_payload = {
        "model": str(payload.get("model") or DEFAULT_MODEL),
        "prompt": str(payload.get("prompt") or ""),
        "stream": False,
        "options": options,
        "keep_alive": payload.get("keep_alive") or KEEP_ALIVE,
    }
    if payload.get("system") is not None:
        upstream_payload["system"] = payload["system"]

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json=upstream_payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    body = response.json()
    body.setdefault("response", "")
    body["proxy_requested_num_predict"] = requested_predict
    body["proxy_internal_num_predict"] = options["num_predict"]
    return body


def _run_with_retry(payload: dict[str, Any]) -> dict[str, Any]:
    first = _call_ollama_generate(payload, retry=False)
    if not _should_retry(first):
        return first

    retry_payload = dict(payload)
    retry_payload["prompt"] = _build_final_only_retry_prompt(str(payload.get("prompt") or ""))
    second = _call_ollama_generate(retry_payload, retry=True)
    second["retry_attempted"] = True
    second["initial_attempt"] = first
    return second


def _finish_reason(body: dict[str, Any]) -> str:
    reason = str(body.get("done_reason") or "").strip().lower()
    if reason == "length":
        return "length"
    return "stop"


def _usage(body: dict[str, Any]) -> dict[str, int]:
    prompt_tokens = int(body.get("prompt_eval_count") or 0)
    completion_tokens = int(body.get("eval_count") or 0)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def _chat_messages_to_prompt(messages: list[dict[str, Any]]) -> tuple[str | None, str]:
    system_parts: list[str] = []
    prompt_parts: list[str] = []
    for message in messages:
        role = str(message.get("role") or "user")
        content = str(message.get("content") or "")
        if role == "system":
            system_parts.append(content)
            continue
        prompt_parts.append(f"{role}: {content}" if role != "user" else content)
    system_prompt = "\n\n".join(part for part in system_parts if part.strip()) or None
    prompt = "\n\n".join(part for part in prompt_parts if part.strip())
    return system_prompt, prompt


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "ollama_base_url": OLLAMA_BASE_URL,
        "model": DEFAULT_MODEL,
        "port": PROXY_PORT,
    }


@app.get("/v1/models")
def models() -> dict[str, Any]:
    created = int(time.time())
    return {
        "object": "list",
        "data": [
            {
                "id": DEFAULT_MODEL,
                "object": "model",
                "created": created,
                "owned_by": "local-proxy",
            }
        ],
    }


@app.post("/api/generate")
async def generate_endpoint(request: Request) -> dict[str, Any]:
    payload = await request.json()
    try:
        body = _run_with_retry(payload)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    body["response"] = _clean_response_text(body)
    body.pop("thinking", None)
    body.pop("reasoning", None)
    return body


@app.post("/v1/chat/completions")
async def chat_completions_endpoint(request: Request) -> dict[str, Any]:
    payload = await request.json()
    messages = payload.get("messages") if isinstance(payload.get("messages"), list) else []
    system_prompt, prompt = _chat_messages_to_prompt(messages)
    generate_payload: dict[str, Any] = {
        "model": str(payload.get("model") or DEFAULT_MODEL),
        "prompt": prompt,
        "system": system_prompt,
        "max_tokens": payload.get("max_tokens"),
        "keep_alive": KEEP_ALIVE,
        "options": {
            "temperature": payload.get("temperature", 0),
            "top_p": payload.get("top_p", 1),
        },
    }
    try:
        body = _run_with_retry(generate_payload)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    content = _clean_response_text(body)
    created = int(time.time())
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": created,
        "model": str(payload.get("model") or DEFAULT_MODEL),
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": _finish_reason(body),
            }
        ],
        "usage": _usage(body),
        "proxy": {
            "retry_attempted": bool(body.get("retry_attempted")),
            "internal_num_predict": body.get("proxy_internal_num_predict"),
            "requested_num_predict": body.get("proxy_requested_num_predict"),
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=PROXY_PORT)