"""Server-side HAL gateway — Moonshot Sprint 2 (all LLM via loopback)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from nr2_browser_security import classify_financial_query

OLLAMA_CHAT = os.environ.get("NR2_OLLAMA_CHAT_URL", "http://127.0.0.1:11434/api/chat")
SOFT_STALE_TTL_HOURS = float(os.environ.get("NR2_SOFT_STALE_TTL_HOURS", "24"))
SOFT_STALE_WATERMARK = (
    "[DATA SOFT-STALE — analytical guidance only; verify amounts against fresh imports before acting]"
)
LANE_MODELS = {
    "chat8b": "hal-chat:8b",
    "reason21b": "hal-reason:21b",
    "escalate30b": "hal-escalate:30b",
}
LANE_HISTORY_KEY = "nr2:hal:lane-history"
_STALE_ACK_KEY = "nr2:hal:stale-ack"

FINANCIAL_OBFUSCATION = re.compile(
    r"(?i)\b(owe|balance|paid|bill|money|amount\s*due|outstanding|insurance|eob|era|adjustment|write[\s-]?off)\b"
)
_AMOUNT_PATTERN = re.compile(r"\$\s*\d[\d,]*(?:\.\d{2})?|\d+\.\d{2}\s*%")
_CLINICAL_PATTERN = re.compile(
    r"(?i)\b(clinical|procedure|tooth|quadrant|cdt|crown|extraction|prophy|periodontal|narrative)\b"
)
_ANALYTICAL_PATTERN = re.compile(
    r"(?i)\b(why|how|explain|analyze|trend|pattern|compare|summary|overview|what if|strategy|plan)\b"
)
_COMPLEXITY_PATTERN = re.compile(
    r"(?i)\b(escalat|complex|multi-step|deep dive|root cause|reconcil|investigate)\b"
)


def build_import_readiness_context(readiness: dict[str, Any]) -> str:
    lines = [
        "[IMPORT_CONTEXT]",
        f"Status: {str(readiness.get('level') or 'unknown').upper()}",
        f"LoadedAt: {readiness.get('loadedAt') or 'unknown'}",
        f"AgeHours: {readiness.get('ageHours') if readiness.get('ageHours') is not None else 'unknown'}",
        f"Ok: {'yes' if readiness.get('ok') else 'no'}",
    ]
    if readiness.get("error"):
        lines.append(f"Error: {readiness['error']}")
    lines.append("You must not provide numeric projections or financial advice when Status is not FRESH.")
    lines.append("[END_IMPORT_CONTEXT]")
    return "\n".join(lines)


def is_financial_query(query: str) -> bool:
    q = str(query or "")
    return classify_financial_query(q) or bool(FINANCIAL_OBFUSCATION.search(q))


def classify_query_intent(query: str) -> str:
    q = str(query or "")
    if _CLINICAL_PATTERN.search(q):
        return "clinical"
    if is_financial_query(q) and not _ANALYTICAL_PATTERN.search(q):
        return "transactional"
    if _ANALYTICAL_PATTERN.search(q) or not is_financial_query(q):
        return "analytical"
    return "transactional"


def is_soft_stale(readiness: dict[str, Any]) -> bool:
    level = str(readiness.get("level") or "unknown")
    if level == "fresh":
        return False
    age = readiness.get("ageHours")
    if age is None:
        return False
    try:
        return float(age) <= SOFT_STALE_TTL_HOURS
    except (TypeError, ValueError):
        return False


def route_by_complexity(query: str, *, shift_context: dict[str, Any] | None = None) -> str:
    q = str(query or "")
    tier = max(1, min(int((shift_context or {}).get("tier") or 1), 7))
    intent = classify_query_intent(q)
    if tier >= 5 or _COMPLEXITY_PATTERN.search(q) or len(q) > 400 or intent == "clinical":
        return "escalate30b"
    if len(q) < 80 and not _ANALYTICAL_PATTERN.search(q) and not _COMPLEXITY_PATTERN.search(q):
        return "chat8b"
    if tier >= 3 or intent == "analytical" or bool(re.search(r"(?i)\b(reason|plan|prioriti|compare)\b", q)):
        return "reason21b"
    return "chat8b"


def resolve_lane(lane_key: str) -> dict[str, str]:
    key = str(lane_key or "chat8b").lower()
    if key not in LANE_MODELS:
        key = "chat8b"
    return {"lane": key, "model": LANE_MODELS[key]}


def redact_financial_numbers(text: str) -> str:
    return _AMOUNT_PATTERN.sub("[AMOUNT REDACTED - STALE DATA]", str(text or ""))


def append_lane_history(store, *, lane: str, model: str, query: str, intent: str) -> None:
    if not store:
        return
    raw = store.get(LANE_HISTORY_KEY)
    try:
        items = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        items = []
    if not isinstance(items, list):
        items = []
    items.append(
        {
            "lane": lane,
            "model": model,
            "intent": intent,
            "queryPreview": str(query or "")[:120],
        }
    )
    store.set(LANE_HISTORY_KEY, json.dumps(items[-100:]))


def list_lane_history(store=None, *, limit: int = 20) -> dict[str, Any]:
    cap = max(1, min(int(limit or 20), 100))
    if not store:
        return {"ok": True, "items": [], "count": 0}
    raw = store.get(LANE_HISTORY_KEY)
    try:
        items = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        items = []
    if not isinstance(items, list):
        items = []
    return {"ok": True, "items": list(reversed(items[-cap:])), "count": len(items)}


def acknowledge_stale(store, *, actor: str = "Staff", reason: str = "") -> dict[str, Any]:
    if not store:
        return {"ok": False, "error": "no_store"}
    from datetime import datetime, timezone

    payload = {
        "at": datetime.now(timezone.utc).isoformat(),
        "actor": str(actor or "Staff"),
        "reason": str(reason or "")[:500],
    }
    store.set(_STALE_ACK_KEY, json.dumps(payload))
    return {"ok": True, "acknowledged": payload}


def call_ollama_chat(
    *,
    model: str,
    messages: list[dict[str, Any]],
    stream: bool = False,
    options: dict[str, Any] | None = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"model": model, "messages": messages, "stream": bool(stream)}
    if options:
        payload["options"] = options
    req = urllib.request.Request(
        OLLAMA_CHAT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if stream:
                chunks: list[str] = []
                for line in resp:
                    try:
                        obj = json.loads(line.decode("utf-8"))
                    except json.JSONDecodeError:
                        continue
                    delta = str((obj.get("message") or {}).get("content") or "")
                    if delta:
                        chunks.append(delta)
                full = "".join(chunks)
                return {"ok": True, "body": {"message": {"content": full}}, "streamed": True}
            body = json.loads(resp.read().decode("utf-8"))
        return {"ok": True, "body": body}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "error": f"ollama_http_{exc.code}", "detail": detail[:2000]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def evaluate_query_stream(
    *,
    query: str,
    readiness: dict[str, Any],
    model: str = "hal-chat:8b",
    system_prompt: str = "",
    messages: list[dict[str, Any]] | None = None,
    options: dict[str, Any] | None = None,
    shift_context: dict[str, Any] | None = None,
    requested_lane: str | None = None,
    store=None,
) -> dict[str, Any]:
    """Gateway gates + Ollama streaming aggregation (server-side)."""
    financial = is_financial_query(query)
    level = str(readiness.get("level") or "unknown")
    intent = classify_query_intent(query)
    soft_stale = is_soft_stale(readiness)
    lane_key = str(requested_lane or route_by_complexity(query, shift_context=shift_context))
    resolved = resolve_lane(lane_key)
    model = str(model or resolved["model"])

    if financial and level != "fresh":
        if intent == "transactional" or not soft_stale:
            return {
                "ok": False,
                "error": "HAL_UNAVAILABLE_STALE_DATA",
                "readiness": readiness,
                "blocked": True,
                "intent": intent,
                "resolvedLane": resolved["lane"],
            }

    chat_messages: list[dict[str, Any]] = []
    if system_prompt:
        chat_messages.append({"role": "system", "content": system_prompt})
    if level != "fresh":
        chat_messages.append({"role": "system", "content": build_import_readiness_context(readiness)})
        if soft_stale and intent in ("analytical", "clinical"):
            chat_messages.append({"role": "system", "content": SOFT_STALE_WATERMARK})
    if messages:
        chat_messages.extend(messages)
    else:
        chat_messages.append({"role": "user", "content": str(query or "")})

    result = call_ollama_chat(model=model, messages=chat_messages, stream=True, options=options)
    if not result.get("ok"):
        return {
            "ok": False,
            "error": result.get("error"),
            "detail": result.get("detail"),
            "resolvedLane": resolved["lane"],
        }

    body = result.get("body") or {}
    text = str((body.get("message") or {}).get("content") or "")
    if level != "fresh" and intent == "transactional":
        text = redact_financial_numbers(text)
    elif level != "fresh" and soft_stale and intent in ("analytical", "clinical"):
        if SOFT_STALE_WATERMARK not in text:
            text = f"{SOFT_STALE_WATERMARK}\n\n{text}"
        text = redact_financial_numbers(text)

    append_lane_history(store, lane=resolved["lane"], model=model, query=query, intent=intent)
    return {
        "ok": True,
        "text": text,
        "message": {"content": text},
        "model": model,
        "readinessLevel": level,
        "intent": intent,
        "softStale": soft_stale,
        "resolvedLane": resolved["lane"],
        "streamed": True,
    }


def evaluate_query(
    *,
    query: str,
    readiness: dict[str, Any],
    model: str = "hal-chat:8b",
    system_prompt: str = "",
    messages: list[dict[str, Any]] | None = None,
    options: dict[str, Any] | None = None,
    shift_context: dict[str, Any] | None = None,
    requested_lane: str | None = None,
    store=None,
) -> dict[str, Any]:
    financial = is_financial_query(query)
    level = str(readiness.get("level") or "unknown")
    intent = classify_query_intent(query)
    soft_stale = is_soft_stale(readiness)
    lane_key = str(requested_lane or route_by_complexity(query, shift_context=shift_context))
    resolved = resolve_lane(lane_key)
    model = str(model or resolved["model"])

    if financial and level != "fresh":
        if intent == "transactional" or (not soft_stale):
            return {
                "ok": False,
                "error": "HAL_UNAVAILABLE_STALE_DATA",
                "readiness": readiness,
                "blocked": True,
                "intent": intent,
                "resolvedLane": resolved["lane"],
            }
        if intent == "analytical" and not soft_stale:
            return {
                "ok": False,
                "error": "HAL_UNAVAILABLE_STALE_DATA",
                "readiness": readiness,
                "blocked": True,
                "intent": intent,
                "resolvedLane": resolved["lane"],
            }

    chat_messages: list[dict[str, Any]] = []
    if system_prompt:
        chat_messages.append({"role": "system", "content": system_prompt})
    if level != "fresh":
        chat_messages.append({"role": "system", "content": build_import_readiness_context(readiness)})
        if soft_stale and intent in ("analytical", "clinical"):
            chat_messages.append({"role": "system", "content": SOFT_STALE_WATERMARK})
    if messages:
        chat_messages.extend(messages)
    else:
        chat_messages.append({"role": "user", "content": str(query or "")})

    result = call_ollama_chat(model=model, messages=chat_messages, stream=False, options=options)
    if not result.get("ok"):
        return {
            "ok": False,
            "error": result.get("error"),
            "detail": result.get("detail"),
            "resolvedLane": resolved["lane"],
        }

    body = result.get("body") or {}
    message = body.get("message") or {}
    text = str(message.get("content") or "")
    if level != "fresh" and intent == "transactional":
        text = redact_financial_numbers(text)
    elif level != "fresh" and soft_stale and intent in ("analytical", "clinical"):
        if SOFT_STALE_WATERMARK not in text:
            text = f"{SOFT_STALE_WATERMARK}\n\n{text}"
        text = redact_financial_numbers(text)

    append_lane_history(store, lane=resolved["lane"], model=model, query=query, intent=intent)

    return {
        "ok": True,
        "text": text,
        "message": message,
        "model": model,
        "readinessLevel": level,
        "intent": intent,
        "softStale": soft_stale,
        "resolvedLane": resolved["lane"],
    }
