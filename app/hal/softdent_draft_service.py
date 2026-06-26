"""SoftDent draft-only service for Phase 2 human-review workflows.

Drafts are local review artifacts only. They never write to SoftDent, submit
claims, or trigger email/fax/upload/Gateway/E-Services actions.
"""

from __future__ import annotations

from typing import Iterable
from uuid import uuid4

from .audit import record_softdent_draft_audit
from .softdent_draft_models import (
    DRAFT_TYPES_REQUIRING_CLINICAL,
    SOFTDENT_DRAFT_TYPES,
    SoftDentDraftArtifact,
    SoftDentDraftRequest,
    SoftDentDraftType,
)
from .softdent_read_broker import (
    SOFTDENT_CLINICAL_READ,
    SOFTDENT_LEDGER_READ,
    SOFTDENT_NARRATIVE_DRAFT,
    SOFTDENT_PATIENT_READ,
    SOFTDENT_READ,
    SoftDentAccessError,
    _normalize_roles,
    _require_roles,
    get_softdent_read_broker,
)
from .softdent_read_models import MISSING_SOFTDENT_AR, PatientContext, SoftDentPatientQuery

DRAFT_DISCLAIMER = (
    "Draft only. Requires human review before any office action. "
    "Not submitted. Not written to SoftDent. "
    "No email, fax, upload, or Gateway/E-Services action was performed."
)


def create_softdent_draft(
    request: SoftDentDraftRequest,
    *,
    actor: str,
    roles: Iterable[str],
) -> SoftDentDraftArtifact:
    if request.draft_type not in SOFTDENT_DRAFT_TYPES:
        raise ValueError(f"Unsupported draft type: {request.draft_type}")

    normalized_roles = _normalize_roles(roles) or set()
    _require_roles(
        normalized_roles,
        {SOFTDENT_READ, SOFTDENT_PATIENT_READ, SOFTDENT_NARRATIVE_DRAFT},
        action="create_softdent_draft",
    )

    needs_clinical = request.draft_type in DRAFT_TYPES_REQUIRING_CLINICAL or request.include_clinical_context
    if needs_clinical:
        _require_roles(normalized_roles, {SOFTDENT_CLINICAL_READ}, action="create_softdent_draft_clinical")

    if request.include_ledger_context:
        _require_roles(normalized_roles, {SOFTDENT_LEDGER_READ}, action="create_softdent_draft_ledger")

    broker = get_softdent_read_broker()
    context = broker.get_patient_context(
        SoftDentPatientQuery(
            question=request.patient_query,
            patient_ref=request.patient_query,
            claim_id=request.claim_id,
            include_clinical_notes=needs_clinical,
            include_ledger=request.include_ledger_context,
            include_narrative_source_facts=request.draft_type == "insurance_narrative_proposal",
        ),
        actor=actor,
        roles=normalized_roles,
        workflow_reason=request.workflow_reason,
        response_mode="draft_review",
        write_audit=True,
    )

    if not context.matched:
        raise ValueError("No patient-specific SoftDent context matched this draft request.")

    artifact = _build_draft_artifact(request.draft_type, context, request=request)
    _audit_draft(artifact=artifact, context=context, actor=actor, roles=normalized_roles, request=request)
    return artifact


def _build_draft_artifact(
    draft_type: SoftDentDraftType,
    context: PatientContext,
    *,
    request: SoftDentDraftRequest,
) -> SoftDentDraftArtifact:
    builders = {
        "clinical_note_proposal": _build_clinical_note_proposal,
        "insurance_narrative_proposal": _build_insurance_narrative_proposal,
        "claim_follow_up_checklist": _build_claim_follow_up_checklist,
        "missing_document_checklist": _build_missing_document_checklist,
        "payer_appeal_prep_summary": _build_payer_appeal_prep_summary,
        "staff_task_recommendation": _build_staff_task_recommendation,
        "internal_patient_summary": _build_internal_patient_summary,
    }
    builder = builders[draft_type]
    return builder(context, request=request)


def _base_limitations(context: PatientContext) -> list[str]:
    limitations = [
        "Draft for review only; HAL did not complete any external or writeback action.",
        DRAFT_DISCLAIMER,
    ]
    if MISSING_SOFTDENT_AR in context.missing_data_codes:
        limitations.append("Patient A/R is unavailable from approved exports; do not state a balance or $0.")
    return limitations


def _source_fact_refs(context: PatientContext, *, include_ledger: bool = False) -> list[str]:
    refs: list[str] = []
    for claim in context.claims:
        if claim.claim_id:
            refs.append(f"claim:{claim.claim_id}")
        elif claim.source_record_id:
            refs.append(f"claim:{claim.source_record_id}")
    for note in context.clinical_notes:
        if note.note_id:
            refs.append(f"clinical_note:{note.note_id}")
        elif note.source_record_id:
            refs.append(f"clinical_note:{note.source_record_id}")
    for procedure in context.procedures:
        if procedure.procedure_id:
            refs.append(f"procedure:{procedure.procedure_id}")
        elif procedure.code:
            refs.append(f"procedure:{procedure.code}")
    if include_ledger and context.ledger is not None:
        refs.append("ledger:patient-ledger")
    return refs


def _build_clinical_note_proposal(context: PatientContext, *, request: SoftDentDraftRequest) -> SoftDentDraftArtifact:
    procedure = next((p.description or p.code for p in context.procedures if p.description or p.code), "documented treatment")
    note_hint = next((n.summary_text for n in context.clinical_notes if n.summary_text), "")
    claim = context.claims[0] if context.claims else None
    body_lines = [
        DRAFT_DISCLAIMER,
        f"Proposed clinical note draft for {context.display_name}.",
        f"Treatment context: {procedure}.",
    ]
    if claim and claim.service_date:
        body_lines.append(f"Service date: {claim.service_date}.")
    if note_hint:
        body_lines.append(f"Supporting documentation summary: {note_hint}")
    body_lines.append("Office staff should verify chart details and edit before any chart entry.")
    checklist = [
        "Verify tooth, surface, and procedure code against the chart.",
        "Confirm clinical findings support the proposed note language.",
        "Have the treating provider review and approve before copying into SoftDent.",
    ]
    return SoftDentDraftArtifact(
        draft_id=f"sdd-{uuid4().hex[:12]}",
        draft_type="clinical_note_proposal",
        patient_label=context.display_name,
        title=f"Clinical note proposal for {context.display_name}",
        body=" ".join(body_lines),
        checklist_items=checklist,
        source_fact_refs=_source_fact_refs(context, include_ledger=request.include_ledger_context),
        missing_data_codes=list(context.missing_data_codes),
        limitations=_base_limitations(context),
        review_required=True,
        external_action_performed=False,
    )


def _build_insurance_narrative_proposal(context: PatientContext, *, request: SoftDentDraftRequest) -> SoftDentDraftArtifact:
    facts = context.narrative_source_facts
    claim = context.claims[0] if context.claims else None
    payer = claim.payer_name if claim else "the payer"
    status = claim.status if claim else "under review"
    procedure = next((p.description or p.code for p in context.procedures if p.description or p.code), "the documented procedure")
    body_lines = [
        DRAFT_DISCLAIMER,
        f"Insurance narrative draft for {context.display_name}.",
        f"The claim concerns {procedure} with payer {payer} and current status {status}.",
    ]
    if facts:
        if facts.claim_facts:
            body_lines.append("Claim facts: " + "; ".join(facts.claim_facts[:3]) + ".")
        if facts.clinical_note_facts:
            body_lines.append("Clinical support: " + " ".join(facts.clinical_note_facts[:2]))
        if facts.limitations:
            body_lines.extend(facts.limitations[:2])
    body_lines.append("This text is for internal review only and must not be submitted as-is.")
    checklist = [
        "Verify payer, procedure, and denial/support details against approved exports.",
        "Add any missing radiographs, perio charting, or narrative attachments before submission.",
        "Have billing staff review and approve before any payer submission.",
    ]
    return SoftDentDraftArtifact(
        draft_id=f"sdd-{uuid4().hex[:12]}",
        draft_type="insurance_narrative_proposal",
        patient_label=context.display_name,
        title=f"Insurance narrative proposal for {context.display_name}",
        body=" ".join(body_lines),
        checklist_items=checklist,
        source_fact_refs=_source_fact_refs(context, include_ledger=request.include_ledger_context),
        missing_data_codes=list(context.missing_data_codes),
        limitations=_base_limitations(context),
        review_required=True,
        external_action_performed=False,
    )


def _build_claim_follow_up_checklist(context: PatientContext, *, request: SoftDentDraftRequest) -> SoftDentDraftArtifact:
    checklist: list[str] = []
    for claim in context.claims[:3]:
        label = claim.claim_id or "claim"
        checklist.append(f"Review {label} status ({claim.status or 'unknown'}) with payer {claim.payer_name or 'unknown'}.")
        if claim.denial_reason:
            checklist.append(f"Address denial/support gap for {label}: {claim.denial_reason}.")
    if not checklist:
        checklist.append("Confirm the matched claim export contains the claim identifiers needed for follow-up.")
    checklist.append("Assign staff owner and target follow-up date after review.")
    body = (
        f"{DRAFT_DISCLAIMER} Claim follow-up checklist for {context.display_name}. "
        "Use this list for internal office coordination only."
    )
    return SoftDentDraftArtifact(
        draft_id=f"sdd-{uuid4().hex[:12]}",
        draft_type="claim_follow_up_checklist",
        patient_label=context.display_name,
        title=f"Claim follow-up checklist for {context.display_name}",
        body=body,
        checklist_items=checklist,
        source_fact_refs=_source_fact_refs(context, include_ledger=request.include_ledger_context),
        missing_data_codes=list(context.missing_data_codes),
        limitations=_base_limitations(context),
        review_required=True,
        external_action_performed=False,
    )


def _build_missing_document_checklist(context: PatientContext, *, request: SoftDentDraftRequest) -> SoftDentDraftArtifact:
    checklist = list(context.documentation_status.missing_items)
    if not checklist:
        checklist.append("No explicit missing-document markers were found; still verify attachments manually.")
    checklist.append("Collect missing attachments before any payer follow-up or appeal.")
    body = (
        f"{DRAFT_DISCLAIMER} Missing-document checklist for {context.display_name}. "
        "This checklist is based on approved export facts only."
    )
    return SoftDentDraftArtifact(
        draft_id=f"sdd-{uuid4().hex[:12]}",
        draft_type="missing_document_checklist",
        patient_label=context.display_name,
        title=f"Missing document checklist for {context.display_name}",
        body=body,
        checklist_items=checklist,
        source_fact_refs=_source_fact_refs(context, include_ledger=request.include_ledger_context),
        missing_data_codes=list(context.missing_data_codes),
        limitations=_base_limitations(context),
        review_required=True,
        external_action_performed=False,
    )


def _build_payer_appeal_prep_summary(context: PatientContext, *, request: SoftDentDraftRequest) -> SoftDentDraftArtifact:
    payer_lines: list[str] = []
    for payer in context.payer_context[:3]:
        statuses = ", ".join(payer.claim_statuses[:3]) if payer.claim_statuses else "unknown"
        payer_lines.append(f"{payer.payer_name or 'Payer'}: statuses {statuses}.")
    denial = next((c.denial_reason for c in context.claims if c.denial_reason), "")
    body_parts = [
        DRAFT_DISCLAIMER,
        f"Payer appeal preparation summary for {context.display_name}.",
        " ".join(payer_lines) if payer_lines else "Payer status facts were limited in approved exports.",
    ]
    if denial:
        body_parts.append(f"Primary denial/support issue to address: {denial}.")
    body_parts.append("Prepare supporting documentation and appeal language for human review only.")
    checklist = [
        "Confirm payer appeal rules and timely filing limits.",
        "Gather clinical notes, radiographs, and claim history referenced in this summary.",
        "Have billing lead approve any appeal draft before external submission.",
    ]
    return SoftDentDraftArtifact(
        draft_id=f"sdd-{uuid4().hex[:12]}",
        draft_type="payer_appeal_prep_summary",
        patient_label=context.display_name,
        title=f"Payer appeal prep summary for {context.display_name}",
        body=" ".join(body_parts),
        checklist_items=checklist,
        source_fact_refs=_source_fact_refs(context, include_ledger=request.include_ledger_context),
        missing_data_codes=list(context.missing_data_codes),
        limitations=_base_limitations(context),
        review_required=True,
        external_action_performed=False,
    )


def _build_staff_task_recommendation(context: PatientContext, *, request: SoftDentDraftRequest) -> SoftDentDraftArtifact:
    tasks = [
        f"Review matched claim context for {context.display_name}.",
        "Confirm missing documentation items and assign collection to front desk or billing.",
    ]
    if any(c.status and c.status.lower() in {"denied", "rejected"} for c in context.claims):
        tasks.append("Prepare narrative/appeal support for denied claim review.")
    if MISSING_SOFTDENT_AR in context.missing_data_codes:
        tasks.append("Do not quote patient A/R; approved exports do not provide a verified balance.")
    body = (
        f"{DRAFT_DISCLAIMER} Staff task recommendations for {context.display_name}. "
        "These are suggested internal tasks only."
    )
    return SoftDentDraftArtifact(
        draft_id=f"sdd-{uuid4().hex[:12]}",
        draft_type="staff_task_recommendation",
        patient_label=context.display_name,
        title=f"Staff task recommendations for {context.display_name}",
        body=body,
        checklist_items=tasks,
        source_fact_refs=_source_fact_refs(context, include_ledger=request.include_ledger_context),
        missing_data_codes=list(context.missing_data_codes),
        limitations=_base_limitations(context),
        review_required=True,
        external_action_performed=False,
    )


def _build_internal_patient_summary(context: PatientContext, *, request: SoftDentDraftRequest) -> SoftDentDraftArtifact:
    claim_count = len(context.claims)
    note_count = len(context.clinical_notes)
    primary_status = context.claims[0].status if context.claims else "unknown"
    payer = context.claims[0].payer_name if context.claims else "unknown"
    body = (
        f"{DRAFT_DISCLAIMER} Internal patient summary for {context.display_name}. "
        f"Matched claims: {claim_count}. Clinical note summaries: {note_count}. "
        f"Primary claim status: {primary_status}. Primary payer: {payer}. "
        "This summary is for authorized internal office review only."
    )
    checklist = [
        "Use this summary to orient staff before deeper chart/claim review.",
        "Verify any time-sensitive payer or documentation follow-up items.",
        "Do not treat this summary as a submitted update or writeback.",
    ]
    return SoftDentDraftArtifact(
        draft_id=f"sdd-{uuid4().hex[:12]}",
        draft_type="internal_patient_summary",
        patient_label=context.display_name,
        title=f"Internal patient summary for {context.display_name}",
        body=body,
        checklist_items=checklist,
        source_fact_refs=_source_fact_refs(context, include_ledger=request.include_ledger_context),
        missing_data_codes=list(context.missing_data_codes),
        limitations=_base_limitations(context),
        review_required=True,
        external_action_performed=False,
    )


def _audit_draft(
    *,
    artifact: SoftDentDraftArtifact,
    context: PatientContext,
    actor: str,
    roles: set[str],
    request: SoftDentDraftRequest,
) -> None:
    claim_ids = [ref.split(":", 1)[1] for ref in artifact.source_fact_refs if ref.startswith("claim:")]
    note_ids = [ref.split(":", 1)[1] for ref in artifact.source_fact_refs if ref.startswith("clinical_note:")]
    ledger_ids = ["patient-ledger"] if request.include_ledger_context else []
    source_metadata = [meta.model_dump() for meta in context.source_metadata]
    record_softdent_draft_audit(
        actor=actor,
        roles_used=sorted(roles),
        draft_type=artifact.draft_type,
        workflow_reason=request.workflow_reason,
        draft_id=artifact.draft_id,
        patient_display_name=artifact.patient_label,
        patient_ref_hash=context.chart_ref_hash,
        chart_ref_hash=context.chart_ref_hash,
        claim_ids=claim_ids,
        clinical_note_ids=note_ids,
        ledger_record_ids=ledger_ids,
        source_adapter="exports",
        source_metadata=source_metadata,
        missing_data_codes=artifact.missing_data_codes,
        review_required=True,
        external_action_performed=False,
    )
