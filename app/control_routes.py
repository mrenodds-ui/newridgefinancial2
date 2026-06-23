from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

import requests
import yaml
from fastapi import APIRouter, Depends

from .auth import AuthenticatedUser, require_roles
from .evaluation.client import get_ollama_runtime_status
from .models import (
    ControlModelSummary,
    ControlRouteAlternative,
    ControlRouteRequest,
    ControlRouteResponse,
    ControlRuntimeStatusResponse,
    ControlScoreRequest,
    ControlScoreResponse,
    ControlWorkflowPreviewRequest,
    ControlWorkflowPreviewResponse,
    ControlWorkflowStep,
    LiteLLMProxyConfigResponse,
    LiteLLMProxyStatusResponse,
    LiteLLMRouteAliasResponse,
)


router = APIRouter()
DEFAULT_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
DEFAULT_LITELLM_PROXY_BASE_URL = os.getenv("LITELLM_PROXY_BASE_URL", "http://127.0.0.1:4000")
LITELLM_ROUTER_CONFIG_PATH = Path(__file__).resolve().parent.parent / "scripts" / "litellm_ollama_router.yaml"
DEFAULT_LITELLM_ROUTING_STRATEGY = "simple-shuffle"


@dataclass
class _ModelCard:
    name: str
    family: str | None
    parameter_size: str | None
    parameter_billions: float | None
    context_length: int | None
    capabilities: list[str]
    heuristic_tags: list[str]


@dataclass
class _LiteLLMRouteGroup:
    alias: str
    purpose: str
    models: list[_ModelCard]
    fallback_aliases: list[str]


def _extract_parameter_billions(name: str, parameter_size: str | None) -> float | None:
    raw_value = parameter_size or name
    match = re.search(r"(\d+(?:\.\d+)?)\s*[Bb]", raw_value)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _build_heuristic_tags(*, family: str | None, parameter_billions: float | None, context_length: int | None, capabilities: list[str]) -> list[str]:
    normalized_family = (family or "").lower()
    normalized_capabilities = {capability.lower() for capability in capabilities}
    tags: list[str] = []

    if "vision" in normalized_capabilities:
        tags.append("vision")
    if "tools" in normalized_capabilities:
        tags.append("tools")
    if any(token in normalized_family for token in ("qwen", "gptoss", "deepseek")):
        tags.append("coding")
    if parameter_billions is not None and parameter_billions >= 60:
        tags.append("large_reasoning")
    if context_length is not None and context_length >= 131072:
        tags.append("long_context")
    if parameter_billions is not None and parameter_billions <= 32:
        tags.append("faster_turnaround")

    return sorted(set(tags))


def _model_summary(card: _ModelCard) -> dict[str, Any]:
    return {
        "name": card.name,
        "family": card.family,
        "parameter_size": card.parameter_size,
        "context_length": card.context_length,
        "capabilities": card.capabilities,
        "heuristic_tags": card.heuristic_tags,
    }


def _fetch_model_catalog(base_url: str, timeout_seconds: int = 5) -> tuple[dict[str, Any], list[_ModelCard]]:
    normalized_base_url = base_url.rstrip("/")
    try:
        response = requests.get(f"{normalized_base_url}/api/tags", timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        runtime_status = get_ollama_runtime_status(normalized_base_url, timeout_seconds=timeout_seconds)
        return runtime_status, []

    raw_models = payload.get("models") if isinstance(payload, dict) else []
    models: list[_ModelCard] = []
    for raw_model in raw_models or []:
        if not isinstance(raw_model, dict):
            continue
        name = str(raw_model.get("name") or raw_model.get("model") or "").strip()
        if not name:
            continue

        details = raw_model.get("details") if isinstance(raw_model.get("details"), dict) else {}
        capabilities = [
            str(capability).strip().lower()
            for capability in raw_model.get("capabilities") or []
            if str(capability).strip()
        ]
        family = str(details.get("family") or "").strip() or None
        parameter_size = str(details.get("parameter_size") or "").strip() or None
        context_length = details.get("context_length")
        if not isinstance(context_length, int):
            context_length = None
        parameter_billions = _extract_parameter_billions(name, parameter_size)
        models.append(
            _ModelCard(
                name=name,
                family=family,
                parameter_size=parameter_size,
                parameter_billions=parameter_billions,
                context_length=context_length,
                capabilities=sorted(set(capabilities)),
                heuristic_tags=_build_heuristic_tags(
                    family=family,
                    parameter_billions=parameter_billions,
                    context_length=context_length,
                    capabilities=capabilities,
                ),
            )
        )

    return {
        "base_url": normalized_base_url,
        "installed": bool(models),
        "running": True,
        "api_reachable": True,
        "installed_models": [model.name for model in models],
        "model_count": len(models),
        "error": None,
    }, models


def _score_model_for_request(card: _ModelCard, payload: ControlRouteRequest) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    if payload.preferred_model and payload.preferred_model.strip().lower() == card.name.lower():
        score += 1000
        reasons.append("Exact preferred model match.")

    wants_vision = payload.requires_vision or payload.task_kind == "vision"
    if wants_vision:
        if "vision" in card.capabilities:
            score += 320
            reasons.append("Supports vision inputs.")
        else:
            score -= 500
            reasons.append("Does not advertise vision support.")

    if payload.requires_tools:
        if "tools" in card.capabilities:
            score += 140
            reasons.append("Supports tool use for workflow steps.")
        else:
            score -= 140
            reasons.append("No tool-use capability detected.")

    family = (card.family or "").lower()
    size = card.parameter_billions or 24.0
    if payload.task_kind == "coding":
        if any(token in family for token in ("qwen", "gptoss", "deepseek")):
            score += 180
            reasons.append("Coding-oriented family or instruction tuning.")
        elif "mistral" in family:
            score += 110
            reasons.append("General reasoning family suitable for code review.")
    elif payload.task_kind in {"analysis", "dashboard", "second_opinion"}:
        if size >= 60:
            score += 180
            reasons.append("Large model favored for deeper analysis and second opinions.")
        elif size >= 24:
            score += 120
            reasons.append("Mid-size reasoning model available for analysis workloads.")
    elif payload.task_kind == "automation":
        if "tools" in card.capabilities:
            score += 160
            reasons.append("Tool support helps automation and workflow orchestration.")
        if size >= 24:
            score += 80
            reasons.append("Enough reasoning headroom for gated automation decisions.")

    if payload.quality_priority == "speed":
        bonus = max(0.0, 170.0 - (size * 4.0))
        score += bonus
        reasons.append("Speed priority biases toward smaller models.")
    elif payload.quality_priority == "quality":
        bonus = min(size * 4.0, 260.0)
        score += bonus
        reasons.append("Quality priority biases toward larger reasoning models.")
    else:
        bonus = max(0.0, 150.0 - abs(size - 30.0) * 3.0)
        score += bonus
        reasons.append("Balanced priority keeps latency and quality in range.")

    if payload.max_context_tokens:
        if card.context_length is not None and card.context_length >= payload.max_context_tokens:
            score += 90
            reasons.append("Meets requested context window.")
        else:
            score -= 220
            reasons.append("Context window is smaller than requested.")
    elif card.context_length is not None and card.context_length >= 131072:
        score += 40
        reasons.append("Long context helps dashboard and workflow prompts.")

    return score, reasons


def _select_model(payload: ControlRouteRequest, models: list[_ModelCard]) -> dict[str, Any]:
    normalized_candidates = {candidate.strip().lower() for candidate in payload.candidate_models if candidate.strip()}
    eligible_models = [model for model in models if model.name.lower() in normalized_candidates] if normalized_candidates else list(models)
    warnings: list[str] = []
    if normalized_candidates and not eligible_models:
        eligible_models = list(models)
        warnings.append("Candidate model filter did not match any installed model, so all installed models were considered.")

    scored = []
    for model in eligible_models:
        score, reasons = _score_model_for_request(model, payload)
        scored.append({"card": model, "score": round(score, 2), "reasons": reasons})

    scored.sort(key=lambda item: item["score"], reverse=True)
    selected = scored[0] if scored else None

    reasoning: list[str] = []
    if selected is not None:
        reasoning.append(f"Selected {selected['card'].name} for {payload.task_kind} with {payload.quality_priority} priority.")
        reasoning.extend(selected["reasons"][:4])
    if payload.preferred_model and selected is not None and payload.preferred_model.strip().lower() != selected["card"].name.lower():
        reasoning.append(f"Preferred model '{payload.preferred_model}' was not selected because another installed model scored higher for the requested constraints.")
    reasoning.extend(warnings)

    return {
        "selected": selected,
        "alternatives": scored[:3],
        "reasoning": reasoning,
        "warnings": warnings,
    }


def _build_runtime_response(runtime_status: dict[str, Any], models: list[_ModelCard]) -> dict[str, Any]:
    coding_choice = _select_model(
        ControlRouteRequest(objective="Route coding diagnostics.", task_kind="coding", quality_priority="balanced", requires_tools=True),
        models,
    )
    analysis_choice = _select_model(
        ControlRouteRequest(objective="Route deep analysis.", task_kind="analysis", quality_priority="quality"),
        models,
    )
    vision_choice = _select_model(
        ControlRouteRequest(objective="Route image or document analysis.", task_kind="vision", requires_vision=True, quality_priority="balanced"),
        models,
    )

    warning = runtime_status.get("error")
    if not warning and not runtime_status.get("installed", False):
        warning = "Ollama is reachable but no installed models were reported."

    return {
        "base_url": runtime_status.get("base_url", DEFAULT_OLLAMA_BASE_URL),
        "api_reachable": bool(runtime_status.get("api_reachable")),
        "installed": bool(runtime_status.get("installed")),
        "running": bool(runtime_status.get("running")),
        "model_count": int(runtime_status.get("model_count") or 0),
        "installed_models": [_model_summary(model) for model in models],
        "suggested_defaults": {
            "coding": coding_choice["selected"]["card"].name if coding_choice.get("selected") else "",
            "analysis": analysis_choice["selected"]["card"].name if analysis_choice.get("selected") else "",
            "vision": vision_choice["selected"]["card"].name if vision_choice.get("selected") else "",
        },
        "warning": warning,
    }


def _litellm_alias_for_request(payload: ControlRouteRequest) -> str:
    if payload.requires_vision or payload.task_kind == "vision":
        return "hal-vision"
    if payload.task_kind == "coding":
        return "hal-coding"
    if payload.task_kind in {"analysis", "dashboard"}:
        return "hal-analysis"
    if payload.task_kind == "second_opinion":
        return "hal-second-opinion"
    return "hal-chat-balanced"


def _pick_top_models(payload: ControlRouteRequest, models: list[_ModelCard], *, max_models: int = 2) -> list[_ModelCard]:
    decision = _select_model(payload, models)
    selected_models: list[_ModelCard] = []
    seen_names: set[str] = set()
    for item in decision.get("alternatives") or []:
        card = item["card"]
        if card.name in seen_names:
            continue
        selected_models.append(card)
        seen_names.add(card.name)
        if len(selected_models) >= max_models:
            break
    return selected_models


def _build_litellm_route_groups(models: list[_ModelCard]) -> list[_LiteLLMRouteGroup]:
    groups = [
        _LiteLLMRouteGroup(
            alias="hal-chat-balanced",
            purpose="Balanced general chat lane exposed through an OpenAI-compatible LiteLLM alias.",
            models=_pick_top_models(
                ControlRouteRequest(objective="Balanced general chat routing.", task_kind="chat", quality_priority="balanced", requires_tools=True),
                models,
                max_models=2,
            ),
            fallback_aliases=["hal-analysis"],
        ),
        _LiteLLMRouteGroup(
            alias="hal-coding",
            purpose="Coding and debugging lane with a coding-first primary model and analysis fallback.",
            models=_pick_top_models(
                ControlRouteRequest(objective="Coding assistance routing.", task_kind="coding", quality_priority="balanced", requires_tools=True),
                models,
                max_models=2,
            ),
            fallback_aliases=["hal-analysis", "hal-chat-balanced"],
        ),
        _LiteLLMRouteGroup(
            alias="hal-analysis",
            purpose="Higher-quality analysis lane for scoring, dashboards, and heavier reasoning tasks.",
            models=_pick_top_models(
                ControlRouteRequest(objective="Deep analysis routing.", task_kind="analysis", quality_priority="quality"),
                models,
                max_models=2,
            ),
            fallback_aliases=["hal-second-opinion", "hal-chat-balanced"],
        ),
        _LiteLLMRouteGroup(
            alias="hal-second-opinion",
            purpose="Second-opinion lane for slower or higher-confidence review passes.",
            models=_pick_top_models(
                ControlRouteRequest(objective="Second opinion routing.", task_kind="second_opinion", quality_priority="quality"),
                models,
                max_models=2,
            ),
            fallback_aliases=["hal-analysis", "hal-chat-balanced"],
        ),
        _LiteLLMRouteGroup(
            alias="hal-vision",
            purpose="Vision-capable lane for screenshots, charts, and document image inspection.",
            models=_pick_top_models(
                ControlRouteRequest(objective="Vision routing.", task_kind="vision", quality_priority="balanced", requires_vision=True),
                models,
                max_models=1,
            ),
            fallback_aliases=["hal-analysis"],
        ),
    ]

    available_aliases = {group.alias for group in groups if group.models}
    return [
        _LiteLLMRouteGroup(
            alias=group.alias,
            purpose=group.purpose,
            models=group.models,
            fallback_aliases=[alias for alias in group.fallback_aliases if alias in available_aliases],
        )
        for group in groups
        if group.models
    ]


def _estimate_litellm_capacity(card: _ModelCard) -> tuple[int, int]:
    size = card.parameter_billions or 24.0
    if size >= 100:
        return 6, 24_000
    if size >= 60:
        return 10, 40_000
    if size >= 30:
        return 18, 90_000
    return 24, 120_000


def _route_group_to_response(group: _LiteLLMRouteGroup) -> dict[str, Any]:
    return {
        "alias": group.alias,
        "purpose": group.purpose,
        "upstream_models": [model.name for model in group.models],
        "fallback_aliases": list(group.fallback_aliases),
    }


def _litellm_startup_command() -> str:
    return f"uv tool run --from \"litellm[proxy]\" litellm --config \"{LITELLM_ROUTER_CONFIG_PATH}\""


def _build_litellm_config_payload(base_url: str, models: list[_ModelCard]) -> dict[str, Any]:
    route_groups = _build_litellm_route_groups(models)
    fallback_entries = [
        {group.alias: list(group.fallback_aliases)}
        for group in route_groups
        if group.fallback_aliases
    ]

    model_list: list[dict[str, Any]] = []
    for group in route_groups:
        for model in group.models:
            rpm, tpm = _estimate_litellm_capacity(model)
            model_list.append(
                {
                    "model_name": group.alias,
                    "litellm_params": {
                        "model": f"ollama_chat/{model.name}",
                        "api_base": "os.environ/OLLAMA_BASE_URL",
                        "rpm": rpm,
                        "tpm": tpm,
                    },
                    "model_info": {
                        "family": model.family or "",
                        "context_length": model.context_length or 0,
                        "heuristic_tags": list(model.heuristic_tags),
                    },
                }
            )

    config = {
        "environment_variables": {
            "OLLAMA_BASE_URL": base_url,
            "LITELLM_PROXY_BASE_URL": DEFAULT_LITELLM_PROXY_BASE_URL,
        },
        "model_list": model_list,
        "litellm_settings": {
            "drop_params": True,
            "request_timeout": 60,
            "force_ipv4": True,
            "json_logs": False,
            "turn_off_message_logging": True,
            "redact_user_api_key_info": True,
        },
        "router_settings": {
            "routing_strategy": DEFAULT_LITELLM_ROUTING_STRATEGY,
            "enable_pre_call_checks": True,
            "fallbacks": fallback_entries,
            "model_group_alias": {
                "chat": "hal-chat-balanced",
                "coding": "hal-coding",
                "analysis": "hal-analysis",
                "second-opinion": "hal-second-opinion",
                "vision": "hal-vision",
            },
        },
        "general_settings": {
            "infer_model_from_keys": True,
            "health_check_details": True,
        },
    }
    return {
        "proxy_base_url": DEFAULT_LITELLM_PROXY_BASE_URL,
        "config_path": str(LITELLM_ROUTER_CONFIG_PATH),
        "routing_strategy": DEFAULT_LITELLM_ROUTING_STRATEGY,
        "auth_expected": bool(os.getenv("LITELLM_MASTER_KEY", "").strip()),
        "startup_command": _litellm_startup_command(),
        "model_aliases": [_route_group_to_response(group) for group in route_groups],
        "openai_compatible_example": {
            "url": f"{DEFAULT_LITELLM_PROXY_BASE_URL.rstrip('/')}/chat/completions",
            "body": {
                "model": "hal-coding",
                "messages": [
                    {
                        "role": "user",
                        "content": "Review this change and tell me the likely bug first.",
                    }
                ],
            },
        },
        "config_yaml": yaml.safe_dump(config, sort_keys=False, allow_unicode=False),
    }


def _fetch_litellm_proxy_status(models: list[_ModelCard]) -> dict[str, Any]:
    payload = _build_litellm_config_payload(DEFAULT_OLLAMA_BASE_URL, models)
    proxy_base_url = DEFAULT_LITELLM_PROXY_BASE_URL.rstrip("/")
    health_endpoint = f"{proxy_base_url}/v1/models"
    headers: dict[str, str] = {}
    master_key = os.getenv("LITELLM_MASTER_KEY", "").strip()
    if master_key:
        headers["Authorization"] = f"Bearer {master_key}"

    try:
        response = requests.get(health_endpoint, timeout=5, headers=headers)
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        return {
            "proxy_base_url": DEFAULT_LITELLM_PROXY_BASE_URL,
            "health_endpoint": health_endpoint,
            "config_path": payload["config_path"],
            "reachable": False,
            "auth_configured": bool(master_key),
            "configured_aliases": payload["model_aliases"],
            "exposed_models": [],
            "startup_command": payload["startup_command"],
            "error": str(exc),
        }

    data = body.get("data") if isinstance(body, dict) else []
    exposed_models = [
        str(item.get("id") or "").strip()
        for item in data or []
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    ]
    return {
        "proxy_base_url": DEFAULT_LITELLM_PROXY_BASE_URL,
        "health_endpoint": health_endpoint,
        "config_path": payload["config_path"],
        "reachable": True,
        "auth_configured": bool(master_key),
        "configured_aliases": payload["model_aliases"],
        "exposed_models": exposed_models,
        "startup_command": payload["startup_command"],
        "error": None,
    }


def _score_response_text(payload: ControlScoreRequest) -> dict[str, Any]:
    text = payload.response_text.strip()
    lowered_text = text.lower()
    required_hits = [term for term in payload.rubric.required_terms if term and term.lower() in lowered_text]
    missing_required = [term for term in payload.rubric.required_terms if term and term.lower() not in lowered_text]
    forbidden_hits = [term for term in payload.rubric.forbidden_terms if term and term.lower() in lowered_text]
    word_count = len(re.findall(r"\b\w+\b", text))
    sentence_count = len(re.findall(r"[.!?](?:\s|$)", text)) or (1 if text else 0)

    notes: list[str] = []
    score = 100.0
    if missing_required:
        score -= min(50.0, 18.0 * len(missing_required))
        notes.append("Required content is missing.")
    if forbidden_hits:
        score -= min(60.0, 25.0 * len(forbidden_hits))
        notes.append("Forbidden content was detected.")
    if word_count < payload.rubric.min_words:
        score -= min(30.0, float(payload.rubric.min_words - word_count))
        notes.append("Response is shorter than the rubric minimum.")
    if payload.rubric.max_words is not None and word_count > payload.rubric.max_words:
        score -= min(20.0, float(word_count - payload.rubric.max_words) / 4.0)
        notes.append("Response is longer than the rubric maximum.")
    if not notes:
        notes.append("Response met the configured rubric checks.")

    score = max(0.0, min(100.0, round(score, 2)))
    passed = (
        not missing_required
        and not forbidden_hits
        and word_count >= payload.rubric.min_words
        and (payload.rubric.max_words is None or word_count <= payload.rubric.max_words)
        and score >= payload.rubric.minimum_score
    )

    return {
        "passed": passed,
        "score": score,
        "word_count": word_count,
        "sentence_count": sentence_count,
        "required_hits": required_hits,
        "missing_required": missing_required,
        "forbidden_hits": forbidden_hits,
        "notes": notes,
    }


@router.get("/api/control/runtime", response_model=ControlRuntimeStatusResponse, include_in_schema=False)
@router.get("/control/runtime", response_model=ControlRuntimeStatusResponse)
def control_runtime_status(user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del user
    runtime_status, models = _fetch_model_catalog(DEFAULT_OLLAMA_BASE_URL)
    return _build_runtime_response(runtime_status, models)


@router.post("/api/control/route", response_model=ControlRouteResponse, include_in_schema=False)
@router.post("/control/route", response_model=ControlRouteResponse)
def control_route_model(payload: ControlRouteRequest, user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del user
    runtime_status, models = _fetch_model_catalog(DEFAULT_OLLAMA_BASE_URL)
    runtime_response = _build_runtime_response(runtime_status, models)
    decision = _select_model(payload, models)
    selected = decision.get("selected")
    alternatives = decision.get("alternatives") or []

    return {
        "available": bool(runtime_status.get("api_reachable")) and bool(models),
        "task_kind": payload.task_kind,
        "quality_priority": payload.quality_priority,
        "selected_model": _model_summary(selected["card"]) if selected else None,
        "fallback_model": alternatives[1]["card"].name if len(alternatives) > 1 else None,
        "litellm_model_alias": _litellm_alias_for_request(payload),
        "litellm_proxy_base_url": DEFAULT_LITELLM_PROXY_BASE_URL,
        "reasoning": decision.get("reasoning") or [],
        "alternatives": [
            {
                "model": _model_summary(item["card"]),
                "score": item["score"],
                "reasons": item["reasons"][:4],
            }
            for item in alternatives
        ],
        "runtime": runtime_response,
    }


@router.post("/api/control/score", response_model=ControlScoreResponse, include_in_schema=False)
@router.post("/control/score", response_model=ControlScoreResponse)
def control_score_response(payload: ControlScoreRequest, user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del user
    return _score_response_text(payload)


@router.post("/api/control/workflows/preview", response_model=ControlWorkflowPreviewResponse, include_in_schema=False)
@router.post("/control/workflows/preview", response_model=ControlWorkflowPreviewResponse)
def control_workflow_preview(payload: ControlWorkflowPreviewRequest, user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del user
    runtime_status, models = _fetch_model_catalog(DEFAULT_OLLAMA_BASE_URL)
    runtime_response = _build_runtime_response(runtime_status, models)
    decision = _select_model(payload, models)
    selected = decision.get("selected")
    blocking_issues: list[str] = []

    if not runtime_status.get("api_reachable"):
        blocking_issues.append(runtime_status.get("error") or "Ollama is not reachable.")
    if not models:
        blocking_issues.append("No installed Ollama models are available for routing.")
    if (payload.requires_vision or payload.task_kind == "vision") and selected and "vision" not in selected["card"].capabilities:
        blocking_issues.append("No installed model satisfied the requested vision capability.")

    execution_endpoint = "/hal9000/second-opinion" if payload.task_kind == "second_opinion" else "/hal9000"
    steps = [
        {
            "step_id": "capture-objective",
            "title": "Capture objective",
            "purpose": "Collect sanitized dashboard context, task intent, and any approval flags.",
            "endpoint": "/control/route",
            "approval_required": False,
        },
        {
            "step_id": "route-model",
            "title": "Route model",
            "purpose": "Select the best local Ollama model for the requested latency, quality, and capability constraints.",
            "endpoint": "/control/route",
            "approval_required": False,
        },
        {
            "step_id": "execute-downstream",
            "title": "Execute downstream lane",
            "purpose": "Send the routed request to the downstream HAL or worker lane with the selected model and contextual inputs.",
            "endpoint": execution_endpoint,
            "approval_required": False,
        },
        {
            "step_id": "score-output",
            "title": "Score output",
            "purpose": f"Evaluate the response against required terms, forbidden terms, and a minimum score of {payload.score_threshold}.",
            "endpoint": "/control/score",
            "approval_required": False,
        },
    ]
    if payload.requires_human_approval or payload.task_kind in {"dashboard", "automation"}:
        steps.append(
            {
                "step_id": "human-review",
                "title": "Human review gate",
                "purpose": "Require an operator to approve or reject the result before any irreversible publication or action.",
                "endpoint": "/control/workflows/preview",
                "approval_required": True,
            }
        )
    steps.append(
        {
            "step_id": "publish-result",
            "title": "Publish result",
            "purpose": "Write the approved result back to the dashboard, queue, or operator workspace.",
            "endpoint": "/control/runtime",
            "approval_required": False,
        }
    )

    return {
        "workflow_id": f"ctrl-{uuid4().hex[:10]}",
        "objective": payload.objective,
        "task_kind": payload.task_kind,
        "recommended_model": selected["card"].name if selected else None,
        "automation_ready": not blocking_issues,
        "score_threshold": payload.score_threshold,
        "blocking_issues": blocking_issues,
        "steps": steps,
        "runtime": runtime_response,
    }


@router.get("/api/control/litellm/config", response_model=LiteLLMProxyConfigResponse, include_in_schema=False)
@router.get("/control/litellm/config", response_model=LiteLLMProxyConfigResponse)
def control_litellm_config(user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del user
    runtime_status, models = _fetch_model_catalog(DEFAULT_OLLAMA_BASE_URL)
    del runtime_status
    return _build_litellm_config_payload(DEFAULT_OLLAMA_BASE_URL, models)


@router.get("/api/control/litellm/status", response_model=LiteLLMProxyStatusResponse, include_in_schema=False)
@router.get("/control/litellm/status", response_model=LiteLLMProxyStatusResponse)
def control_litellm_status(user: AuthenticatedUser = Depends(require_roles("hal:operator"))):
    del user
    runtime_status, models = _fetch_model_catalog(DEFAULT_OLLAMA_BASE_URL)
    del runtime_status
    return _fetch_litellm_proxy_status(models)