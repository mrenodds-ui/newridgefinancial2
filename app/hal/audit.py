from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .storage import get_hal_audit as get_hal_audit_from_storage
from .storage import get_recent_hal_audits as get_recent_hal_audits_from_storage
from .storage import insert_hal_audit


@dataclass(slots=True)
class HalAuditEntry:
    audit_id: str
    created_at_utc: str
    actor: str
    mode: str
    sanitized_question: str
    retrieval_ids: list[str]
    response_summary: str

def record_hal_audit(
    *,
    actor: str,
    mode: str,
    sanitized_question: str,
    retrieval_ids: list[str],
    response_summary: str,
) -> dict[str, Any]:
    entry = HalAuditEntry(
        audit_id=f"hal-{uuid4().hex[:12]}",
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        actor=actor,
        mode=mode,
        sanitized_question=sanitized_question,
        retrieval_ids=retrieval_ids,
        response_summary=response_summary,
    )
    payload = asdict(entry)
    insert_hal_audit(payload)
    return payload


def get_recent_hal_audits(limit: int = 20) -> list[dict[str, Any]]:
    return get_recent_hal_audits_from_storage(limit=limit)


def get_hal_audit(audit_id: str) -> dict[str, Any] | None:
    return get_hal_audit_from_storage(audit_id)