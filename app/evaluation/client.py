from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable, TypeVar

import requests

from .audio import speak_text, speak_text_async

T = TypeVar("T")


class ResponseValidationError(ValueError):
    pass


def load_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_text_file(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()


def extract_json_object(text: str) -> str:
    stripped = text.strip()
    fenced_match = re.fullmatch(r"```(?:json)?\s*(\{.*\})\s*```", stripped, flags=re.DOTALL)
    if fenced_match:
        return fenced_match.group(1).strip()
    return stripped


def parse_json_object_response(response_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(extract_json_object(response_text))
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", response_text, flags=re.DOTALL)
        if not match:
            raise ResponseValidationError("Expected a top-level JSON object in the model response.") from None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise ResponseValidationError("Expected valid JSON output from the model.") from exc

    if not isinstance(payload, dict):
        raise ResponseValidationError("Expected the model to return a JSON object.")

    return payload


def validate_json_object_response(
    response_text: str,
    *,
    required_keys: list[str] | None = None,
) -> dict[str, Any]:
    payload = parse_json_object_response(response_text)
    missing_keys = [key for key in required_keys or [] if key not in payload]
    if missing_keys:
        raise ResponseValidationError(f"Missing required JSON keys: {', '.join(missing_keys)}")
    return payload


def build_retry_prompt(*, original_prompt: str, previous_output: str, error_message: str) -> str:
    return (
        "Your previous output failed validation. Correct it and try again. "
        "Return only the corrected answer, with no explanation or markdown fences.\n\n"
        f"Original instructions:\n{original_prompt}\n\n"
        f"Validation error:\n{error_message}\n\n"
        f"Previous output:\n{previous_output}\n"
    )


def build_options(profile: dict[str, Any], seed: int | None = None) -> dict[str, Any]:
    env_num_gpu_override = __import__("os").getenv("OLLAMA_NUM_GPU_OVERRIDE")
    options = {
        "temperature": profile.get("temperature", 0),
        "top_p": profile.get("top_p", 1),
    }
    for option_name in (
        "top_k",
        "min_p",
        "repeat_penalty",
        "repeat_last_n",
        "mirostat",
        "mirostat_tau",
        "mirostat_eta",
        "num_ctx",
        "num_predict",
        "tfs_z",
        "typical_p",
        "num_gpu",
    ):
        if profile.get(option_name) is not None:
            options[option_name] = profile[option_name]

    if env_num_gpu_override is not None and env_num_gpu_override.strip() != "":
        try:
            options["num_gpu"] = int(env_num_gpu_override.strip())
        except ValueError:
            # Ignore invalid env override and preserve profile/default options.
            pass
    if seed is not None:
        options["seed"] = seed
    elif profile.get("seed") is not None:
        options["seed"] = profile["seed"]
    return options


def strip_thinking_tags(response_text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()


def should_retry_after_thinking_only_response(raw_response_text: str, cleaned_response_text: str) -> bool:
    return cleaned_response_text == "" and bool(raw_response_text.strip()) and "<think" in raw_response_text.lower()


def build_final_only_retry_prompt(prompt: str) -> str:
    return (
        f"{prompt}\n\n"
        "IMPORTANT: Return only the final answer. Do not include <think> tags, hidden reasoning, or scratchpad. "
        "If you started internal reasoning, suppress it and answer directly in the requested format."
    )


def extract_ollama_generate_metrics(body: dict[str, Any]) -> dict[str, int | float | None]:
    load_duration_ns = int(body.get("load_duration") or 0)
    prompt_eval_duration_ns = int(body.get("prompt_eval_duration") or 0)
    eval_duration_ns = int(body.get("eval_duration") or 0)
    total_duration_ns = int(body.get("total_duration") or 0)
    prompt_eval_count = int(body.get("prompt_eval_count") or 0)
    eval_count = int(body.get("eval_count") or 0)

    average_output_token_duration_ns = (eval_duration_ns / eval_count) if eval_count else 0.0
    ttft_estimate_ns = load_duration_ns + prompt_eval_duration_ns + average_output_token_duration_ns

    return {
        "load_duration_ns": load_duration_ns,
        "prompt_eval_duration_ns": prompt_eval_duration_ns,
        "eval_duration_ns": eval_duration_ns,
        "total_duration_ns": total_duration_ns,
        "prompt_eval_count": prompt_eval_count,
        "eval_count": eval_count,
        "time_to_first_token_estimate_seconds": round(ttft_estimate_ns / 1_000_000_000, 4) if ttft_estimate_ns else 0.0,
        "output_tokens_per_second": round(eval_count / (eval_duration_ns / 1_000_000_000), 2) if eval_count and eval_duration_ns else None,
        "prompt_tokens_per_second": round(prompt_eval_count / (prompt_eval_duration_ns / 1_000_000_000), 2) if prompt_eval_count and prompt_eval_duration_ns else None,
        "end_to_end_tokens_per_second": round((prompt_eval_count + eval_count) / (total_duration_ns / 1_000_000_000), 2) if (prompt_eval_count or eval_count) and total_duration_ns else None,
    }


def generate_response_result(
    base_url: str,
    profile: dict[str, Any],
    prompt: str,
    timeout_seconds: int,
    seed: int | None = None,
) -> dict[str, Any]:
    system_prompt_path = profile.get("system_prompt_path")
    system_prompt = load_text_file(Path(system_prompt_path)) if system_prompt_path else None
    prompt_prefix = str(profile.get("prompt_prefix") or "")
    active_prompt = f"{prompt_prefix}{prompt}" if prompt_prefix else prompt
    retry_attempted = False
    initial_body: dict[str, Any] | None = None
    request_model = str(profile.get("litellm_model") or profile["model"]) if _is_litellm_proxy_base_url(base_url) else profile["model"]
    body = run_ollama_generate(
        base_url=base_url,
        model=request_model,
        prompt=active_prompt,
        system_prompt=system_prompt,
        options=build_options(profile, seed=seed),
        keep_alive=profile.get("keep_alive"),
        think=profile.get("think"),
        timeout_seconds=timeout_seconds,
    )
    response_text = body.get("response", "")
    if profile.get("strip_thinking_tags", False):
        cleaned_response_text = strip_thinking_tags(response_text)
        if should_retry_after_thinking_only_response(response_text, cleaned_response_text):
            retry_attempted = True
            initial_body = body
            body = run_ollama_generate(
                base_url=base_url,
                model=request_model,
                prompt=build_final_only_retry_prompt(active_prompt),
                system_prompt=system_prompt,
                options=build_options(profile, seed=seed),
                keep_alive=profile.get("keep_alive"),
                think=profile.get("think"),
                timeout_seconds=timeout_seconds,
            )
            response_text = body.get("response", "")
            cleaned_response_text = strip_thinking_tags(response_text)
        response_text = cleaned_response_text
    metrics = extract_ollama_generate_metrics(body)
    if retry_attempted:
        metrics["retry_attempted"] = True
        metrics["initial_attempt_metrics"] = extract_ollama_generate_metrics(initial_body or {})
    return {
        "response_text": response_text,
        "metrics": metrics,
        "raw_body": body,
    }


def resolve_profile(config: dict[str, Any], alias: str) -> dict[str, Any]:
    try:
        return config["profiles"][alias]
    except KeyError as exc:
        raise KeyError(f"Unknown model profile alias: {alias}") from exc


def run_ollama_generate(
    *,
    base_url: str,
    model: str,
    prompt: str,
    system_prompt: str | None,
    options: dict[str, Any],
    keep_alive: str | int | None,
    think: bool | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    if _is_litellm_proxy_base_url(base_url):
        return _run_litellm_chat_completion(
            base_url=base_url,
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
            options=options,
            timeout_seconds=timeout_seconds,
        )

    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": options,
    }
    if system_prompt:
        payload["system"] = system_prompt
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive
    if think is not None:
        payload["think"] = bool(think)

    response = requests.post(
        f"{base_url.rstrip('/')}/api/generate",
        json=payload,
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    body = response.json()
    body.setdefault("response", "")
    return body


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _is_litellm_proxy_base_url(base_url: str) -> bool:
    proxy_base_url = os.getenv("LITELLM_PROXY_BASE_URL", "").strip()
    return bool(proxy_base_url) and _normalize_base_url(proxy_base_url) == _normalize_base_url(base_url)


def _run_litellm_chat_completion(
    *,
    base_url: str,
    model: str,
    prompt: str,
    system_prompt: str | None,
    options: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if options.get("temperature") is not None:
        payload["temperature"] = options["temperature"]
    if options.get("top_p") is not None:
        payload["top_p"] = options["top_p"]
    if options.get("num_predict") is not None:
        payload["max_tokens"] = options["num_predict"]
    if options.get("seed") is not None:
        payload["seed"] = options["seed"]

    headers: dict[str, str] = {}
    master_key = os.getenv("LITELLM_MASTER_KEY", "").strip()
    if master_key:
        headers["Authorization"] = f"Bearer {master_key}"

    response = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        json=payload,
        timeout=timeout_seconds,
        headers=headers or None,
    )
    response.raise_for_status()
    body = response.json()

    choices = body.get("choices") if isinstance(body, dict) else []
    message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
    usage = body.get("usage") if isinstance(body, dict) and isinstance(body.get("usage"), dict) else {}

    return {
        "response": str((message or {}).get("content") or ""),
        "prompt_eval_count": int(usage.get("prompt_tokens") or 0),
        "eval_count": int(usage.get("completion_tokens") or 0),
        "total_duration": 0,
        "prompt_eval_duration": 0,
        "eval_duration": 0,
        "load_duration": 0,
        "provider": "litellm_proxy",
        "raw_body": body,
    }


def generate_response(
    base_url: str,
    profile: dict[str, Any],
    prompt: str,
    timeout_seconds: int,
    seed: int | None = None,
) -> str:
    return generate_response_result(
        base_url=base_url,
        profile=profile,
        prompt=prompt,
        timeout_seconds=timeout_seconds,
        seed=seed,
    )["response_text"]


def generate_response_with_validation(
    *,
    base_url: str,
    profile: dict[str, Any],
    prompt: str,
    timeout_seconds: int,
    validator: Callable[[str], T],
    max_attempts: int = 2,
    seed: int | None = None,
) -> tuple[str, T]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    active_prompt = prompt
    last_error: ResponseValidationError | None = None

    for attempt in range(1, max_attempts + 1):
        response_text = generate_response(
            base_url=base_url,
            profile=profile,
            prompt=active_prompt,
            timeout_seconds=timeout_seconds,
            seed=seed,
        )
        try:
            return response_text, validator(response_text)
        except ResponseValidationError as exc:
            last_error = exc
            if attempt >= max_attempts:
                break
            active_prompt = build_retry_prompt(
                original_prompt=prompt,
                previous_output=response_text,
                error_message=str(exc),
            )

    assert last_error is not None
    raise last_error


def run_python_validation(
    parsed_payload: dict[str, Any],
    *,
    validator: Callable[[dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    if validator is None:
        return {"passed": True, "details": "No Python validation callback was provided."}

    result = validator(parsed_payload)
    if result is None:
        return {"passed": True, "details": "Python validation completed successfully."}
    if isinstance(result, bool):
        if not result:
            raise ResponseValidationError("Python validation failed.")
        return {"passed": True, "details": "Python validation completed successfully."}
    if isinstance(result, str):
        return {"passed": True, "details": result}
    if isinstance(result, dict):
        passed = result.get("passed", True)
        if not passed:
            raise ResponseValidationError(str(result.get("error") or result.get("details") or "Python validation failed."))
        normalized = dict(result)
        normalized.setdefault("passed", True)
        return normalized

    raise TypeError("validator must return None, bool, str, or dict[str, Any]")


def run_structured_output_workflow(
    *,
    base_url: str,
    parser_profile: dict[str, Any],
    narrator_profile: dict[str, Any],
    source_text: str,
    parse_instructions: str,
    summary_instructions: str,
    timeout_seconds: int,
    required_keys: list[str] | None = None,
    validator: Callable[[dict[str, Any]], Any] | None = None,
    max_parse_attempts: int = 3,
    seed: int | None = None,
    parser_base_url: str | None = None,
    narrator_base_url: str | None = None,
) -> dict[str, Any]:
    parse_prompt = (
        "Convert the source text into a single JSON object that follows the instructions exactly. "
        "Do not wrap the JSON in markdown fences.\n\n"
        f"Parse instructions:\n{parse_instructions}\n\n"
        f"Source text:\n{source_text}\n"
    )

    def parser_validator(response_text: str) -> dict[str, Any]:
        parsed_payload = validate_json_object_response(response_text, required_keys=required_keys)
        validation_result = run_python_validation(parsed_payload, validator=validator)
        return {
            "parsed_payload": parsed_payload,
            "validation_result": validation_result,
        }

    parser_output_text, parser_result = generate_response_with_validation(
        base_url=parser_base_url or base_url,
        profile=parser_profile,
        prompt=parse_prompt,
        timeout_seconds=timeout_seconds,
        validator=parser_validator,
        max_attempts=max_parse_attempts,
        seed=seed,
    )

    summary_prompt = (
        "Write the final response using the validated structured data and the Python validation notes.\n\n"
        f"Summary instructions:\n{summary_instructions}\n\n"
        "Validated structured data:\n"
        f"{json.dumps(parser_result['parsed_payload'], indent=2, sort_keys=True)}\n\n"
        "Validation notes:\n"
        f"{json.dumps(parser_result['validation_result'], indent=2, sort_keys=True)}\n"
    )
    summary_text = generate_response(
        base_url=narrator_base_url or base_url,
        profile=narrator_profile,
        prompt=summary_prompt,
        timeout_seconds=timeout_seconds,
        seed=seed,
    )

    return {
        "parse_prompt": parse_prompt,
        "parse_output_text": parser_output_text,
        "parsed_payload": parser_result["parsed_payload"],
        "validation_result": parser_result["validation_result"],
        "summary_prompt": summary_prompt,
        "summary_text": summary_text,
    }


def check_ollama_available(base_url: str, timeout_seconds: int = 10) -> tuple[bool, str | None]:
    try:
        health_response = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout_seconds)
        health_response.raise_for_status()
    except requests.RequestException as exc:
        return False, str(exc)
    return True, None


def get_ollama_runtime_status(base_url: str, timeout_seconds: int = 10) -> dict[str, Any]:
    normalized_base_url = base_url.rstrip("/")
    try:
        health_response = requests.get(f"{normalized_base_url}/api/tags", timeout=timeout_seconds)
        health_response.raise_for_status()
        payload = health_response.json()
    except (requests.RequestException, ValueError) as exc:
        return {
            "base_url": normalized_base_url,
            "installed": False,
            "running": False,
            "api_reachable": False,
            "installed_models": [],
            "model_count": 0,
            "error": str(exc),
        }

    models = payload.get("models") if isinstance(payload, dict) else []
    installed_models = [
        str(model.get("name") or "").strip()
        for model in models or []
        if isinstance(model, dict) and str(model.get("name") or "").strip()
    ]
    return {
        "base_url": normalized_base_url,
        "installed": bool(installed_models),
        "running": True,
        "api_reachable": True,
        "installed_models": installed_models,
        "model_count": len(installed_models),
        "error": None,
    }


def handle_ai_response(
    *,
    base_url: str,
    profile: dict[str, Any],
    prompt: str,
    timeout_seconds: int,
    seed: int | None = None,
    speak: bool = False,
    async_playback: bool = True,
    voice_id: str | None = None,
) -> str:
    response_text = generate_response(
        base_url=base_url,
        profile=profile,
        prompt=prompt,
        timeout_seconds=timeout_seconds,
        seed=seed,
    )

    if speak:
        if async_playback:
            speak_text_async(response_text, voice_id=voice_id)
        else:
            speak_text(response_text, voice_id=voice_id)

    return response_text
