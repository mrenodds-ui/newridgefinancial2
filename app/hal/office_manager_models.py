from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

OfficeManagerTaskCategory = Literal[
    "claim",
    "patient_prep",
    "documentation",
    "treatment_plan",
    "hygiene_recall",
    "compliance",
    "vendor",
    "report",
    "other",
]

OfficeManagerTaskStatus = Literal["open", "in_progress", "blocked", "completed", "dismissed"]

OfficeManagerTaskPriority = Literal["low", "normal", "high", "urgent"]

OfficeManagerAttentionSeverity = Literal["info", "warning", "critical"]

OfficeManagerAttentionCategory = Literal[
    "claims_follow_up",
    "missing_documentation",
    "drafts_review",
    "local_packets",
    "source_health",
    "revenue",
    "system_health",
    "local_tasks",
    "treatment_plan",
    "hygiene_recall",
    "compliance",
    "vendor",
    "reports",
    "accounts_receivable",
]

OFFICE_MANAGER_SAFETY_DISCLAIMER = (
    "Local office-manager workflow only. Draft only where applicable. Requires human review. "
    "Local only. not_submitted. Not written to SoftDent. "
    "No email/fax/upload/Gateway action performed. No external delivery."
)


class OfficeManagerAttentionItem(BaseModel):
    item_id: str
    category: OfficeManagerAttentionCategory
    severity: OfficeManagerAttentionSeverity = "info"
    title: str
    detail: str
    action_hint: str = ""
    source_key: str = ""
    missing_data_codes: list[str] = Field(default_factory=list)
    count: int | None = None
    local_only: bool = True
    external_action_performed: bool = False


class OfficeManagerAttentionResponse(BaseModel):
    generated_at_utc: str
    summary: str
    safety_disclaimer: str = OFFICE_MANAGER_SAFETY_DISCLAIMER
    items: list[OfficeManagerAttentionItem] = Field(default_factory=list)
    missing_data_codes: list[str] = Field(default_factory=list)
    local_only: bool = True
    external_action_performed: bool = False
    softdent_writeback_performed: bool = False
    submission_status: Literal["not_submitted"] = "not_submitted"


class OfficeManagerTaskCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=4000)
    category: OfficeManagerTaskCategory = "other"
    priority: OfficeManagerTaskPriority = "normal"
    patient_label: str | None = Field(default=None, max_length=200)
    claim_id: str | None = Field(default=None, max_length=128)
    source_refs: list[str] = Field(default_factory=list)
    missing_data_codes: list[str] = Field(default_factory=list)
    due_date: str | None = Field(default=None, max_length=32)
    assigned_to: str | None = Field(default=None, max_length=120)


class OfficeManagerTaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    category: OfficeManagerTaskCategory | None = None
    status: OfficeManagerTaskStatus | None = None
    priority: OfficeManagerTaskPriority | None = None
    patient_label: str | None = Field(default=None, max_length=200)
    claim_id: str | None = Field(default=None, max_length=128)
    source_refs: list[str] | None = None
    missing_data_codes: list[str] | None = None
    due_date: str | None = Field(default=None, max_length=32)
    assigned_to: str | None = Field(default=None, max_length=120)


class OfficeManagerTaskResponse(BaseModel):
    task_id: str
    title: str
    description: str = ""
    category: OfficeManagerTaskCategory
    status: OfficeManagerTaskStatus
    priority: OfficeManagerTaskPriority
    patient_label: str | None = None
    claim_id: str | None = None
    source_refs: list[str] = Field(default_factory=list)
    missing_data_codes: list[str] = Field(default_factory=list)
    due_date: str | None = None
    assigned_to: str | None = None
    created_by: str
    created_at_utc: str
    updated_at_utc: str
    local_only: bool = True
    external_action_performed: bool = False
    softdent_writeback_performed: bool = False


class OfficeManagerTaskListResponse(BaseModel):
    items: list[OfficeManagerTaskResponse] = Field(default_factory=list)
    total_count: int = 0
    local_only: bool = True
    external_action_performed: bool = False
    softdent_writeback_performed: bool = False
    submission_status: Literal["not_submitted"] = "not_submitted"


class OfficeManagerTaskMetricsResponse(BaseModel):
    open_count: int = 0
    in_progress_count: int = 0
    blocked_count: int = 0
    completed_count: int = 0
    dismissed_count: int = 0
    urgent_open_count: int = 0
    local_only: bool = True
    external_action_performed: bool = False
    softdent_writeback_performed: bool = False
