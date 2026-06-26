from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .storage import get_hal_audit as get_hal_audit_from_storage
from .storage import get_recent_hal_audits as get_recent_hal_audits_from_storage
from .storage import get_recent_softdent_draft_audits as get_recent_softdent_draft_audits_from_storage
from .storage import get_recent_softdent_packet_audits as get_recent_softdent_packet_audits_from_storage
from .storage import get_recent_softdent_record_audits as get_recent_softdent_record_audits_from_storage
from .storage import get_softdent_draft_audit as get_softdent_draft_audit_from_storage
from .storage import get_softdent_packet_audit as get_softdent_packet_audit_from_storage
from .storage import get_softdent_record_audit as get_softdent_record_audit_from_storage
from .storage import insert_hal_audit
from .storage import insert_office_manager_task_audit
from .storage import insert_softdent_draft_audit
from .storage import insert_softdent_packet_audit
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


def record_softdent_draft_audit(
    *,
    actor: str,
    roles_used: list[str],
    draft_type: str,
    workflow_reason: str,
    draft_id: str,
    patient_display_name: str | None = None,
    patient_ref_hash: str | None = None,
    chart_ref_hash: str | None = None,
    claim_ids: list[str] | None = None,
    clinical_note_ids: list[str] | None = None,
    ledger_record_ids: list[str] | None = None,
    source_adapter: str = "exports",
    source_metadata: list[dict[str, Any]] | None = None,
    missing_data_codes: list[str] | None = None,
    review_required: bool = True,
    external_action_performed: bool = False,
) -> dict[str, Any]:
    """Persist a draft-only SoftDent audit event.

    Phase 2 drafts are local review artifacts only. ``external_action_performed``
    must remain ``False`` and this wrapper does not store raw clinical note bodies,
    raw CSV rows, or secrets.
    """
    if external_action_performed:
        raise ValueError("SoftDent Phase 2 draft audit cannot record an external action.")
    payload: dict[str, Any] = {
        "draft_id": draft_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "roles_used": list(roles_used or []),
        "draft_type": draft_type,
        "workflow_reason": workflow_reason,
        "patient_display_name": patient_display_name,
        "patient_ref_hash": patient_ref_hash,
        "chart_ref_hash": chart_ref_hash,
        "claim_ids": list(claim_ids or []),
        "clinical_note_ids": list(clinical_note_ids or []),
        "ledger_record_ids": list(ledger_record_ids or []),
        "source_adapter": source_adapter,
        "source_metadata": list(source_metadata or []),
        "missing_data_codes": list(missing_data_codes or []),
        "review_required": bool(review_required),
        "external_action_performed": False,
    }
    insert_softdent_draft_audit(payload)
    return payload


def get_recent_softdent_draft_audits(limit: int = 20) -> list[dict[str, Any]]:
    return get_recent_softdent_draft_audits_from_storage(limit=limit)


def get_softdent_draft_audit(draft_id: str) -> dict[str, Any] | None:
    return get_softdent_draft_audit_from_storage(draft_id)


def record_softdent_packet_audit(
    *,
    actor: str,
    roles_used: list[str],
    packet_type: str,
    source_draft_id: str,
    packet_id: str,
    patient_display_name: str | None = None,
    patient_ref_hash: str | None = None,
    chart_ref_hash: str | None = None,
    claim_ids: list[str] | None = None,
    clinical_note_ids: list[str] | None = None,
    ledger_record_ids: list[str] | None = None,
    source_fact_refs: list[str] | None = None,
    missing_data_codes: list[str] | None = None,
    approval_attestation: dict[str, Any] | None = None,
    submission_status: str = "not_submitted",
    external_action_performed: bool = False,
    softdent_writeback_performed: bool = False,
    local_only: bool = True,
) -> dict[str, Any]:
    """Persist a local approved packet audit event.

    Phase 3 packets remain local and not submitted. This wrapper rejects any
    external action, SoftDent writeback, or non-not_submitted submission status.
    """
    if external_action_performed:
        raise ValueError("SoftDent Phase 3 packet audit cannot record an external action.")
    if softdent_writeback_performed:
        raise ValueError("SoftDent Phase 3 packet audit cannot record SoftDent writeback.")
    if submission_status != "not_submitted":
        raise ValueError("SoftDent Phase 3 packet audit must keep submission_status=not_submitted.")
    payload: dict[str, Any] = {
        "packet_id": packet_id,
        "source_draft_id": source_draft_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "roles_used": list(roles_used or []),
        "packet_type": packet_type,
        "patient_display_name": patient_display_name,
        "patient_ref_hash": patient_ref_hash,
        "chart_ref_hash": chart_ref_hash,
        "claim_ids": list(claim_ids or []),
        "clinical_note_ids": list(clinical_note_ids or []),
        "ledger_record_ids": list(ledger_record_ids or []),
        "source_fact_refs": list(source_fact_refs or []),
        "missing_data_codes": list(missing_data_codes or []),
        "approval_attestation": dict(approval_attestation or {}),
        "submission_status": "not_submitted",
        "external_action_performed": False,
        "softdent_writeback_performed": False,
        "local_only": bool(local_only),
    }
    insert_softdent_packet_audit(payload)
    return payload


def get_recent_softdent_packet_audits(limit: int = 20) -> list[dict[str, Any]]:
    return get_recent_softdent_packet_audits_from_storage(limit=limit)


def get_softdent_packet_audit(packet_id: str) -> dict[str, Any] | None:
    return get_softdent_packet_audit_from_storage(packet_id)


def record_office_manager_task_audit(
    *,
    task_id: str,
    actor: str,
    roles_used: list[str],
    action: str,
    status: str,
    title: str,
    category: str,
    external_action_performed: bool = False,
    softdent_writeback_performed: bool = False,
) -> dict[str, Any]:
    if external_action_performed:
        raise ValueError("Office manager task audit cannot record an external action.")
    if softdent_writeback_performed:
        raise ValueError("Office manager task audit cannot record SoftDent writeback.")
    payload: dict[str, Any] = {
        "event_id": f"omta-{uuid4().hex[:12]}",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "task_id": task_id,
        "actor": actor,
        "roles_used": list(roles_used or []),
        "action": action,
        "status": status,
        "title": title,
        "category": category,
        "local_only": True,
        "external_action_performed": False,
        "softdent_writeback_performed": False,
    }
    insert_office_manager_task_audit(payload)
    return payload
