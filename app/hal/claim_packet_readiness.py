"""Local read-only Claim Packet Readiness assessment for HAL office-manager workflows."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from app.hal.claim_packet_readiness_models import (
    ClaimPacketLocalDraftStatus,
    ClaimPacketReadinessItem,
    ClaimPacketReadinessPriority,
    ClaimPacketReadinessResponse,
    ClaimPacketReadinessSafety,
    ClaimPacketReadinessStatus,
    ClaimPacketReadinessSummary,
)
from app.insurance_narratives.case_packet import build_insurance_narrative_case_packet
from app.insurance_narratives.data_adapter import (
    FIXTURE_CATALOG,
    SOFTDENT_NARRATIVE_CLAIMS_FILENAME,
    InsuranceNarrativeDataAdapter,
    InsuranceNarrativeScope,
    _export_row_claim_id,
    _export_row_patient_ref,
    _parse_export_procedure_ids,
    _read_scoped_export_csv,
    _resolve_softdent_narrative_export_dir,
    default_fixture_adapter,
    softdent_export_file_adapter,
)
from app.insurance_narratives.schemas import InsuranceNarrativeCasePacket, NarrativeMissingDataItem

READINESS_SAFETY = ClaimPacketReadinessSafety()

READINESS_STAFF_LABELS: dict[str, str] = {
    "missing_claim_export": "Claims export missing",
    "missing_claim_status": "Claim status missing",
    "missing_denial_reason": "Denial reason missing",
    "missing_clinical_note": "Clinical note missing",
    "missing_narrative": "Narrative missing",
    "missing_radiograph_or_photo": "Radiograph/photo missing",
    "missing_perio_chart": "Perio chart or probing depths missing",
    "missing_procedure_facts": "Procedure facts missing",
    "missing_patient_match": "Patient match missing",
    "missing_human_review": "Human review required",
}

NARRATIVE_TO_READINESS_CODE: dict[str, str] = {
    "missing_softdent_claims_export": "missing_claim_export",
    "missing_scoped_claim_row": "missing_claim_export",
    "missing_claim_record": "missing_claim_export",
    "missing_claim_status": "missing_claim_status",
    "missing_scoped_claim_status_row": "missing_claim_status",
    "missing_softdent_claim_status_export": "missing_claim_status",
    "invalid_softdent_claim_status_export": "missing_claim_status",
    "missing_denial_letter": "missing_denial_reason",
    "missing_clinical_narrative": "missing_narrative",
    "missing_softdent_clinical_notes_export": "missing_clinical_note",
    "missing_scoped_clinical_note_rows": "missing_clinical_note",
    "invalid_softdent_clinical_notes_export": "missing_clinical_note",
    "missing_radiograph": "missing_radiograph_or_photo",
    "missing_periodontal_chart": "missing_perio_chart",
    "missing_scoped_procedure_rows": "missing_procedure_facts",
    "missing_softdent_procedures_export": "missing_procedure_facts",
    "missing_patient_record": "missing_patient_match",
}

EXPORT_LEVEL_BLOCKING_CODES = frozenset(
    {
        "missing_softdent_claims_export",
        "missing_patient_record",
        "missing_claim_record",
        "missing_scoped_claim_row",
    }
)

OPEN_CLAIM_STATUSES = frozenset({"denied", "pending", "submitted", "open", "in process", "in_process"})


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def readiness_label(code: str) -> str:
    return READINESS_STAFF_LABELS.get(code, code.replace("_", " ").strip())


def map_missing_data_to_readiness_codes(missing_data: list[NarrativeMissingDataItem]) -> list[str]:
    codes: list[str] = []
    seen: set[str] = set()
    for item in missing_data:
        mapped = NARRATIVE_TO_READINESS_CODE.get(item.code)
        if mapped is None and item.blocking:
            mapped = item.code.replace("missing_softdent_", "missing_").replace("missing_scoped_", "missing_")
        if mapped is None:
            continue
        if mapped in seen:
            continue
        seen.add(mapped)
        codes.append(mapped)
    return codes


def _resolve_readiness_adapter() -> InsuranceNarrativeDataAdapter:
    configured = os.environ.get("INSURANCE_NARRATIVE_SOFTDENT_EXPORT_DIR", "").strip()
    if configured:
        return softdent_export_file_adapter(configured)
    export_dir = _resolve_softdent_narrative_export_dir()
    claims_path = export_dir / SOFTDENT_NARRATIVE_CLAIMS_FILENAME
    if claims_path.is_file():
        return softdent_export_file_adapter(export_dir)
    return default_fixture_adapter()


def discover_claim_scopes(adapter: InsuranceNarrativeDataAdapter | None = None) -> list[tuple[str, str, list[str]]]:
    resolved = adapter or _resolve_readiness_adapter()
    if resolved.adapter_name == "softdent_export_file":
        export_dir = getattr(resolved, "export_dir", _resolve_softdent_narrative_export_dir())
        rows = _read_scoped_export_csv(Path(export_dir) / SOFTDENT_NARRATIVE_CLAIMS_FILENAME)
        if not rows:
            return []
        scopes: list[tuple[str, str, list[str]]] = []
        for row in rows:
            patient_ref = _export_row_patient_ref(row)
            claim_id = _export_row_claim_id(row)
            if not patient_ref or not claim_id:
                continue
            status = str(row.get("claim_status") or "").strip().lower()
            if status in {"paid", "closed", "complete", "completed"}:
                continue
            procedure_ids = _parse_export_procedure_ids(str(row.get("procedure_ids") or ""))
            scopes.append((patient_ref, claim_id, procedure_ids))
        return scopes

    scopes = []
    for patient_ref, patient_data in FIXTURE_CATALOG.items():
        claims = patient_data.get("claims") or {}
        for claim_id, claim_data in claims.items():
            procedures = claim_data.get("procedures") or []
            procedure_ids = [str(proc.get("procedure_id") or "") for proc in procedures if proc.get("procedure_id")]
            scopes.append((patient_ref, claim_id, procedure_ids))
    return scopes


def _available_items_from_packet(packet: InsuranceNarrativeCasePacket) -> list[str]:
    items: list[str] = []
    if packet.claim and packet.claim.status:
        items.append(f"Claim status: {packet.claim.status}")
    if packet.claim and packet.claim.payer_name:
        items.append(f"Payer: {packet.claim.payer_name}")
    if packet.claim and packet.claim.denial_reason:
        items.append("Denial reason available")
    if packet.procedures:
        items.append(f"{len(packet.procedures)} procedure fact(s) available")
    if any(fact.source_type == "clinical_note" for fact in packet.source_facts):
        items.append("Clinical note available")
    if packet.attachments:
        available_attachments = [item.label for item in packet.attachments if item.available]
        if available_attachments:
            items.append(f"Attachment(s): {', '.join(available_attachments)}")
    if packet.source_facts:
        items.append(f"{len(packet.source_facts)} verified source fact(s)")
    return items


def _source_basis_from_packet(packet: InsuranceNarrativeCasePacket) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for fact in packet.source_facts:
        label = fact.source_label.strip()
        if not label or label in seen:
            continue
        seen.add(label)
        labels.append(label)
    if packet.audit_metadata.adapter_name == "softdent_export_file":
        labels.append("SoftDent claims export")
    elif packet.audit_metadata.adapter_name == "fixture":
        labels.append("Local fixture claim facts")
    return labels


def _priority_for_status(status: ClaimPacketReadinessStatus, claim_status: str | None) -> ClaimPacketReadinessPriority:
    if status == "blocked":
        return "high"
    if (claim_status or "").strip().lower() == "denied":
        return "high"
    if status == "needs_review":
        return "normal"
    return "low"


def _local_draft_status(
    *,
    status: ClaimPacketReadinessStatus,
    can_prepare_local_draft: bool,
) -> ClaimPacketLocalDraftStatus:
    if not can_prepare_local_draft:
        return "needs_facts"
    if status == "ready":
        return "draft_available"
    if status == "needs_review":
        return "draft_available"
    return "none"


def _staff_summary_for_status(
    *,
    status: ClaimPacketReadinessStatus,
    missing_labels: list[str],
    can_prepare_local_draft: bool,
) -> str:
    if status == "ready":
        return "Packet appears ready for human review. Nothing has been submitted or sent."
    if status == "needs_review":
        if can_prepare_local_draft:
            return "Local draft can be prepared. Staff must review before use. Nothing has been submitted or sent."
        if missing_labels:
            return f"Needs review: {missing_labels[0]}."
        return "Needs review before use. Nothing has been submitted or sent."
    if missing_labels:
        return f"Blocked: {missing_labels[0]}."
    return "Blocked until required local facts are available."


def _recommended_actions(
    *,
    status: ClaimPacketReadinessStatus,
    missing_codes: list[str],
    can_prepare_local_draft: bool,
) -> list[str]:
    actions: list[str] = []
    if "missing_claim_export" in missing_codes:
        actions.append("Import the SoftDent claims export before assessing packet readiness.")
    if "missing_clinical_note" in missing_codes:
        actions.append("Import or locate the clinical note for staff review.")
    if "missing_denial_reason" in missing_codes:
        actions.append("Import claim status or denial details for staff review.")
    if "missing_radiograph_or_photo" in missing_codes:
        actions.append("Confirm whether a radiograph or photo is available locally.")
    if "missing_perio_chart" in missing_codes:
        actions.append("Confirm whether a perio chart or probing depths are available locally.")
    if can_prepare_local_draft and status in {"ready", "needs_review"}:
        actions.append("Prepare a local draft for human review.")
    if status in {"ready", "needs_review"}:
        actions.append("Review packet facts before any operational use.")
    actions.append("Nothing has been submitted or sent.")
    deduped: list[str] = []
    seen: set[str] = set()
    for action in actions:
        if action in seen:
            continue
        seen.add(action)
        deduped.append(action)
    return deduped


def assess_claim_packet_readiness(
    *,
    patient_ref: str,
    claim_id: str,
    procedure_ids: list[str] | None = None,
    actor: str = "hal_system",
    adapter: InsuranceNarrativeDataAdapter | None = None,
) -> ClaimPacketReadinessItem:
    resolved_adapter = adapter or _resolve_readiness_adapter()
    packet = build_insurance_narrative_case_packet(
        patient_ref=patient_ref,
        claim_id=claim_id,
        procedure_ids=procedure_ids,
        narrative_type="claim_packet_readiness",
        actor=actor,
        adapter=resolved_adapter,
    )

    narrative_missing = packet.missing_data
    readiness_missing_codes = map_missing_data_to_readiness_codes(narrative_missing)
    missing_labels = [readiness_label(code) for code in readiness_missing_codes]

    blocking_narrative_codes = {item.code for item in narrative_missing if item.blocking}
    export_blocked = bool(blocking_narrative_codes & EXPORT_LEVEL_BLOCKING_CODES) or "missing_claim_export" in readiness_missing_codes

    has_claim = packet.claim is not None and bool(packet.claim.claim_id)
    has_claim_status = bool(packet.claim and packet.claim.status)
    has_procedures = bool(packet.procedures)
    has_clinical_note = any(fact.source_type == "clinical_note" for fact in packet.source_facts)
    has_denial_reason = bool(packet.claim and packet.claim.denial_reason)
    blocking_missing = any(item.blocking for item in narrative_missing)

    can_prepare_local_draft = has_claim and not export_blocked and "missing_patient_match" not in readiness_missing_codes

    if export_blocked or not has_claim or blocking_missing:
        status: ClaimPacketReadinessStatus = "blocked"
    elif has_claim_status and has_procedures and not blocking_missing:
        if has_clinical_note or has_denial_reason:
            status = "ready"
        else:
            status = "needs_review"
            if "missing_clinical_note" not in readiness_missing_codes and not has_clinical_note:
                readiness_missing_codes.append("missing_clinical_note")
                missing_labels.append(readiness_label("missing_clinical_note"))
    elif has_claim_status or packet.source_facts:
        status = "needs_review"
    else:
        status = "blocked"

    if status in {"ready", "needs_review"}:
        readiness_missing_codes.append("missing_human_review")
        if readiness_label("missing_human_review") not in missing_labels:
            missing_labels.append(readiness_label("missing_human_review"))

    blockers = [label for label in missing_labels if status == "blocked"]
    priority = _priority_for_status(status, packet.claim.status if packet.claim else None)
    draft_status = _local_draft_status(status=status, can_prepare_local_draft=can_prepare_local_draft)

    return ClaimPacketReadinessItem(
        packet_id=packet.packet_id,
        patient_ref=packet.patient.patient_ref,
        patient_label=packet.patient.label,
        claim_ref=packet.claim.claim_id if packet.claim else claim_id,
        procedure_refs=[proc.procedure_id for proc in packet.procedures],
        status=status,
        priority=priority,
        blockers=blockers,
        missing_items=missing_labels,
        available_items=_available_items_from_packet(packet),
        recommended_next_actions=_recommended_actions(
            status=status,
            missing_codes=readiness_missing_codes,
            can_prepare_local_draft=can_prepare_local_draft,
        ),
        can_prepare_local_draft=can_prepare_local_draft,
        local_draft_status=draft_status,
        safety=READINESS_SAFETY.model_copy(deep=True),
        source_basis=_source_basis_from_packet(packet),
        staff_summary=_staff_summary_for_status(
            status=status,
            missing_labels=missing_labels,
            can_prepare_local_draft=can_prepare_local_draft,
        ),
    )


def build_claim_packet_readiness_response(
    *,
    actor: str = "hal_system",
    adapter: InsuranceNarrativeDataAdapter | None = None,
) -> ClaimPacketReadinessResponse:
    resolved_adapter = adapter or _resolve_readiness_adapter()
    scopes = discover_claim_scopes(resolved_adapter)
    items: list[ClaimPacketReadinessItem] = []

    if not scopes:
        items.append(
            ClaimPacketReadinessItem(
                packet_id="claim-packet-readiness-no-export",
                status="blocked",
                priority="high",
                blockers=[readiness_label("missing_claim_export")],
                missing_items=[readiness_label("missing_claim_export")],
                recommended_next_actions=[
                    "Import the SoftDent claims export before assessing packet readiness.",
                    "Nothing has been submitted or sent.",
                ],
                can_prepare_local_draft=False,
                local_draft_status="needs_facts",
                safety=READINESS_SAFETY.model_copy(deep=True),
                source_basis=["SoftDent claims export"],
                staff_summary=f"Blocked: {readiness_label('missing_claim_export')}.",
            )
        )
    else:
        for patient_ref, claim_id, procedure_ids in scopes:
            items.append(
                assess_claim_packet_readiness(
                    patient_ref=patient_ref,
                    claim_id=claim_id,
                    procedure_ids=procedure_ids or None,
                    actor=actor,
                    adapter=resolved_adapter,
                )
            )

    summary = ClaimPacketReadinessSummary(
        ready_count=sum(1 for item in items if item.status == "ready"),
        needs_review_count=sum(1 for item in items if item.status == "needs_review"),
        blocked_count=sum(1 for item in items if item.status == "blocked"),
        total_count=len(items),
    )
    return ClaimPacketReadinessResponse(
        generated_at_utc=_utc_now_iso(),
        summary=summary,
        items=items,
        safety=READINESS_SAFETY.model_copy(deep=True),
    )


def build_claim_packet_readiness_answer(*, actor: str = "hal_system") -> str:
    payload = build_claim_packet_readiness_response(actor=actor)
    summary = payload.summary
    lines = [
        "Claim packet readiness (local only):",
        f"- Ready: {summary.ready_count}",
        f"- Needs review: {summary.needs_review_count}",
        f"- Blocked: {summary.blocked_count}",
        "",
        "HAL can prepare a local packet and draft. Staff must review before use. Nothing has been submitted or sent.",
    ]
    examples = payload.items[:4]
    if examples:
        lines.append("")
        lines.append("Examples:")
        for item in examples:
            headline = item.staff_summary or readiness_label(item.status.replace("_", " "))
            if item.claim_ref:
                headline = f"{item.claim_ref}: {headline}"
            lines.append(f"- {headline}")
    return "\n".join(lines)
