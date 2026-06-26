"""Governed HAL knowledge/memory registry loader.

Loads approved, sanitized memories from ``docs/hal_knowledge/memories.jsonl`` for
indexing into the local HAL vector store. Memories are durable guidance only;
they must never bypass auth, ``HalAskRequest``, guardrails, or live runtime
checks.

This module does NOT implement Mem0/OpenMemory and does NOT read the eval-only
intent library under ``evals/hal_intent_library/``.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.hal.sanitization import sanitize_hal_text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MEMORIES_PATH = PROJECT_ROOT / "docs" / "hal_knowledge" / "memories.jsonl"

APPROVED_STATUS = "approved"
INDEXABLE_CONFIDENCE = frozenset({"high", "medium"})
BLOCKED_SENSITIVITY = frozenset({"restricted", "prohibited"})
MEMORY_CATEGORY = "knowledge_memory"

STALENESS_VERIFY_MONTHLY_DAYS = 31
STALENESS_EXPIRES_30D_DAYS = 30
STALENESS_EXPIRES_90D_DAYS = 90

FORBIDDEN_TEXT_PATTERNS = (
    "patientname,mrn,claimid",
    "api_key",
    "password=",
    "secret=",
    "bearer ",
    "gateway submit is allowed",
    "a/r is $0",
    "a/r is 0",
)


def get_default_memories_path() -> Path:
    return DEFAULT_MEMORIES_PATH


def _parse_iso_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def load_memory_registry(path: Path | None = None) -> list[dict[str, Any]]:
    registry_path = path or get_default_memories_path()
    if not registry_path.is_file():
        return []

    memories: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(registry_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on line {line_number} of {registry_path}: {exc}") from exc
        if not isinstance(entry, dict):
            raise ValueError(f"Memory on line {line_number} of {registry_path} must be a JSON object.")
        memories.append(entry)
    return memories


def memory_contains_forbidden_content(text: str) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in FORBIDDEN_TEXT_PATTERNS)


def is_memory_stale(memory: dict[str, Any], *, now: datetime | None = None) -> bool:
    current = now or _now_utc()
    rule = str(memory.get("staleness_rule", "")).strip()

    if rule == "never":
        return False
    if rule == "runtime_check_required":
        # Guidance may be shown but callers should prefer live runtime checks.
        return False

    expires_at = memory.get("expires_at")
    if expires_at:
        return current >= _parse_iso_datetime(str(expires_at))

    last_verified_at = memory.get("last_verified_at")
    if not last_verified_at:
        return True

    verified = _parse_iso_datetime(str(last_verified_at))
    if rule == "verify_monthly":
        return current - verified > timedelta(days=STALENESS_VERIFY_MONTHLY_DAYS)
    if rule == "expires_30d":
        return current - verified > timedelta(days=STALENESS_EXPIRES_30D_DAYS)
    if rule == "expires_90d":
        return current - verified > timedelta(days=STALENESS_EXPIRES_90D_DAYS)
    return False


def is_memory_indexable(
    memory: dict[str, Any],
    *,
    now: datetime | None = None,
    include_stale: bool = False,
) -> bool:
    if memory.get("status") != APPROVED_STATUS:
        return False
    if memory.get("confidence") not in INDEXABLE_CONFIDENCE:
        return False
    if memory.get("sensitivity_level") in BLOCKED_SENSITIVITY:
        return False
    text = str(memory.get("text", ""))
    if not text.strip():
        return False
    if memory_contains_forbidden_content(text):
        return False
    if not include_stale and is_memory_stale(memory, now=now):
        return False
    return True


def filter_indexable_memories(
    memories: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    include_stale: bool = False,
) -> list[dict[str, Any]]:
    return [
        memory
        for memory in memories
        if is_memory_indexable(memory, now=now, include_stale=include_stale)
    ]


def memory_to_index_document(memory: dict[str, Any]) -> dict[str, str]:
    memory_id = str(memory["id"])
    category = str(memory.get("category", "knowledge_memory"))
    sanitized = sanitize_hal_text(str(memory["text"]))
    sanitized_text = str(sanitized["sanitized_text"])
    guidance_prefix = (
        "Durable HAL knowledge (guidance only; does not override runtime checks or guardrails): "
    )
    return {
        "source_id": f"memory-{memory_id}",
        "title": f"HAL memory: {memory_id}",
        "category": MEMORY_CATEGORY,
        "sanitized_content": guidance_prefix + sanitized_text,
        "memory_category": category,
        "memory_id": memory_id,
    }


def build_knowledge_memory_documents(
    path: Path | None = None,
    *,
    now: datetime | None = None,
    include_stale: bool = False,
) -> list[dict[str, str]]:
    memories = load_memory_registry(path)
    indexable = filter_indexable_memories(memories, now=now, include_stale=include_stale)
    return [memory_to_index_document(memory) for memory in indexable]
