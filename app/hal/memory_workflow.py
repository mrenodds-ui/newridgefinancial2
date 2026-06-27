"""Governed HAL knowledge-memory proposal and approval workflow.

Local SQLite storage with append-only audit events. Proposals are sanitized and
validated before persistence; nothing is auto-approved from chat.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.hal.knowledge_memory import (
    APPROVED_STATUS,
    invalidate_approved_memory_cache,
    is_memory_indexable,
    memory_contains_forbidden_content,
)
from app.hal.sanitization import sanitize_hal_text
from app.hal.storage import (
    get_hal_memory,
    insert_hal_memory,
    insert_hal_memory_event,
    list_hal_memories,
    update_hal_memory,
)

PROPOSED_STATUS = "proposed"
REVOKED_STATUS = "revoked"
DEPRECATED_STATUS = "deprecated"

DEFAULT_MUST_NOT_OVERRIDE = ("guardrails", "auth", "runtime_status", "hal_ask_request")
ALLOWED_CATEGORIES = frozenset(
    {
        "known_workflows",
        "operator_playbooks",
        "deployment_notes",
        "project_architecture",
    }
)


class MemoryWorkflowError(ValueError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_memory_id() -> str:
    return f"office-{uuid4().hex[:12]}"


def _new_event_id() -> str:
    return f"memevt-{uuid4().hex[:12]}"


def validate_memory_proposal_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if len(stripped) < 10:
        raise MemoryWorkflowError("Memory text must be at least 10 characters after sanitization.")
    if len(stripped) > 2000:
        raise MemoryWorkflowError("Memory text must be 2000 characters or fewer.")

    sanitized = sanitize_hal_text(stripped)
    sanitized_text = str(sanitized["sanitized_text"]).strip()
    if len(sanitized_text) < 10:
        raise MemoryWorkflowError("Memory text is too short after sanitization.")
    if memory_contains_forbidden_content(sanitized_text):
        raise MemoryWorkflowError(
            "Memory text contains forbidden patterns (PHI-like rows, secrets, or unsafe external-action language)."
        )
    if sanitized.get("findings"):
        raise MemoryWorkflowError(
            "Memory text still contains patient identifiers or sensitive fields after sanitization; "
            "rephrase as office workflow guidance only."
        )
    return {"sanitized_text": sanitized_text, "findings": sanitized.get("findings", [])}


def _build_memory_record(
    *,
    memory_id: str,
    text: str,
    actor: str,
    category: str,
    source: str,
    status: str,
    confidence: str,
    approved_by: str | None = None,
    approved_at_utc: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    timestamp = _now_iso()
    return {
        "memory_id": memory_id,
        "id": memory_id,
        "category": category,
        "text": text,
        "source": source,
        "created_at_utc": timestamp,
        "created_at": timestamp,
        "last_verified_at_utc": timestamp,
        "last_verified_at": timestamp,
        "confidence": confidence,
        "scope": "hal",
        "staleness_rule": "verify_monthly",
        "expires_at_utc": None,
        "expires_at": None,
        "sensitivity_level": "internal_safe",
        "status": status,
        "must_not_override": list(DEFAULT_MUST_NOT_OVERRIDE),
        "proposed_by": actor,
        "approved_by": approved_by,
        "approved_at_utc": approved_at_utc,
        "notes": notes,
    }


def _record_event(
    *,
    memory_id: str,
    actor: str,
    event_type: str,
    snapshot: dict[str, Any],
    previous_status: str | None,
    new_status: str | None,
    note: str,
) -> dict[str, Any]:
    event = {
        "event_id": _new_event_id(),
        "memory_id": memory_id,
        "created_at_utc": _now_iso(),
        "actor": actor,
        "event_type": event_type,
        "previous_status": previous_status,
        "new_status": new_status,
        "note": note,
        "snapshot": snapshot,
    }
    insert_hal_memory_event(event)
    return event


def propose_hal_memory(
    *,
    actor: str,
    text: str,
    category: str = "known_workflows",
    source: str = "operator chat proposal",
    proposed_from_question: str | None = None,
) -> dict[str, Any]:
    if category not in ALLOWED_CATEGORIES:
        raise MemoryWorkflowError(f"Unsupported memory category: {category}")
    validated = validate_memory_proposal_text(text)
    sanitized_text = str(validated["sanitized_text"])
    memory_id = _new_memory_id()
    provenance = source
    if proposed_from_question:
        provenance = f"{source}; from sanitized ask request"
    record = _build_memory_record(
        memory_id=memory_id,
        text=sanitized_text,
        actor=actor,
        category=category,
        source=provenance,
        status=PROPOSED_STATUS,
        confidence="medium",
        notes="Awaiting admin review before indexing.",
    )
    insert_hal_memory(record)
    _record_event(
        memory_id=memory_id,
        actor=actor,
        event_type="proposed",
        snapshot=record,
        previous_status=None,
        new_status=PROPOSED_STATUS,
        note="Memory proposed for governed review.",
    )
    return get_hal_memory(memory_id) or record


def approve_hal_memory(*, memory_id: str, actor: str, note: str = "") -> dict[str, Any]:
    memory = get_hal_memory(memory_id)
    if memory is None:
        raise MemoryWorkflowError(f"Unknown memory id: {memory_id}")
    if memory["status"] != PROPOSED_STATUS:
        raise MemoryWorkflowError(f"Memory {memory_id} is not in proposed status.")

    approved_at = _now_iso()
    updates = {
        "status": APPROVED_STATUS,
        "confidence": "medium",
        "last_verified_at_utc": approved_at,
        "last_verified_at": approved_at,
        "approved_by": actor,
        "approved_at_utc": approved_at,
        "notes": note.strip() or "Approved for governed HAL retrieval.",
    }
    update_hal_memory(memory_id, updates)
    approved = get_hal_memory(memory_id)
    if approved is None:
        raise MemoryWorkflowError(f"Failed to load approved memory {memory_id}.")
    if not is_memory_indexable(approved):
        raise MemoryWorkflowError(f"Approved memory {memory_id} failed indexability checks.")

    _record_event(
        memory_id=memory_id,
        actor=actor,
        event_type="approved",
        snapshot=approved,
        previous_status=PROPOSED_STATUS,
        new_status=APPROVED_STATUS,
        note=note.strip() or "Approved for governed HAL retrieval.",
    )
    invalidate_approved_memory_cache()
    return approved


def revoke_hal_memory(*, memory_id: str, actor: str, note: str = "") -> dict[str, Any]:
    memory = get_hal_memory(memory_id)
    if memory is None:
        raise MemoryWorkflowError(f"Unknown memory id: {memory_id}")
    if memory["status"] == REVOKED_STATUS:
        raise MemoryWorkflowError(f"Memory {memory_id} is already revoked.")

    previous_status = str(memory["status"])
    updates = {
        "status": REVOKED_STATUS,
        "notes": note.strip() or "Revoked; excluded from retrieval.",
    }
    update_hal_memory(memory_id, updates)
    revoked = get_hal_memory(memory_id)
    if revoked is None:
        raise MemoryWorkflowError(f"Failed to load revoked memory {memory_id}.")

    _record_event(
        memory_id=memory_id,
        actor=actor,
        event_type="revoked",
        snapshot=revoked,
        previous_status=previous_status,
        new_status=REVOKED_STATUS,
        note=note.strip() or "Revoked; excluded from retrieval.",
    )
    invalidate_approved_memory_cache()
    return revoked


def list_governed_hal_memories(*, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    return list_hal_memories(status=status, limit=limit)
