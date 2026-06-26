from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .storage import get_hal_audit as get_hal_audit_from_storage
from .storage import get_recent_hal_audits as get_recent_hal_audits_from_storage
from .storage import get_recent_softdent_record_audits as get_recent_softdent_record_audits_from_storage
from .storage import get_softdent_record_audit as get_softdent_record_audit_from_storage
from .storage import insert_hal_audit
from .storage import insert_softdent_record_audit


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


def record_softdent_read_audit(
    *,
    actor: str,
    roles_used: list[str],
    workflow_reason: str,
    response_mode: str,
    patient_display_name: str | None = None,
    patient_ref_hash: str | None = None,
    chart_ref_hash: str | None = None,
    claim_ids: list[str] | None = None,
    clinical_note_ids: list[str] | None = None,
    ledger_record_ids: list[str] | None = None,
    source_adapter: str = "exports",
    source_metadata: list[dict[str, Any]] | None = None,
    missing_data_codes: list[str] | None = None,
    external_action_performed: bool = False,
) -> dict[str, Any]:
    """Persist a record-level SoftDent read audit event.

    Phase 1 never performs external actions, so ``external_action_performed``
    must remain ``False``. This wrapper intentionally stores only bounded
    identifiers, hashes, and metadata; it never stores raw clinical note text,
    raw CSV rows, or secrets.
    """
    if external_action_performed:
        raise ValueError("SoftDent Phase 1 read audit cannot record an external action.")
    payload: dict[str, Any] = {
        "event_id": f"sdr-{uuid4().hex[:12]}",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "roles_used": list(roles_used or []),
        "workflow_reason": workflow_reason,
        "response_mode": response_mode,
        "patient_display_name": patient_display_name,
        "patient_ref_hash": patient_ref_hash,
        "chart_ref_hash": chart_ref_hash,
        "claim_ids": list(claim_ids or []),
        "clinical_note_ids": list(clinical_note_ids or []),
        "ledger_record_ids": list(ledger_record_ids or []),
        "source_adapter": source_adapter,
        "source_metadata": list(source_metadata or []),
        "missing_data_codes": list(missing_data_codes or []),
        "external_action_performed": False,
    }
    insert_softdent_record_audit(payload)
    return payload


def get_recent_softdent_read_audits(limit: int = 20) -> list[dict[str, Any]]:
    return get_recent_softdent_record_audits_from_storage(limit=limit)


def get_softdent_read_audit(event_id: str) -> dict[str, Any] | None:
    return get_softdent_record_audit_from_storage(event_id)