from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.hal.office_manager_models import OFFICE_MANAGER_SAFETY_DISCLAIMER

ClaimPacketReadinessStatus = Literal["ready", "needs_review", "blocked"]
ClaimPacketReadinessPriority = Literal["low", "normal", "high"]
ClaimPacketLocalDraftStatus = Literal["none", "draft_available", "needs_facts"]


class ClaimPacketReadinessSafety(BaseModel):
    local_only: bool = True
    not_submitted: bool = True
    human_review_required: bool = True
    external_delivery_allowed: bool = False
    softdent_writeback_allowed: bool = False
    payer_contact_allowed: bool = False


class ClaimPacketReadinessItem(BaseModel):
    packet_id: str
    patient_ref: str | None = None
    patient_label: str | None = None
    claim_ref: str | None = None
    procedure_refs: list[str] = Field(default_factory=list)
    status: ClaimPacketReadinessStatus
    priority: ClaimPacketReadinessPriority = "normal"
    blockers: list[str] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)
    available_items: list[str] = Field(default_factory=list)
    recommended_next_actions: list[str] = Field(default_factory=list)
    can_prepare_local_draft: bool = False
    local_draft_status: ClaimPacketLocalDraftStatus = "none"
    safety: ClaimPacketReadinessSafety = Field(default_factory=ClaimPacketReadinessSafety)
    source_basis: list[str] = Field(default_factory=list)
    staff_summary: str = ""


class ClaimPacketReadinessSummary(BaseModel):
    ready_count: int = 0
    needs_review_count: int = 0
    blocked_count: int = 0
    total_count: int = 0


class ClaimPacketReadinessResponse(BaseModel):
    generated_at_utc: str
    summary: ClaimPacketReadinessSummary
    items: list[ClaimPacketReadinessItem] = Field(default_factory=list)
    safety_disclaimer: str = OFFICE_MANAGER_SAFETY_DISCLAIMER
    safety: ClaimPacketReadinessSafety = Field(default_factory=ClaimPacketReadinessSafety)
    local_only: bool = True
    submission_status: Literal["not_submitted"] = "not_submitted"
