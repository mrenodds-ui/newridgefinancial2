from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.hal.audit import record_office_manager_task_audit
from app.hal.office_manager_models import (
    OfficeManagerTaskCreateRequest,
    OfficeManagerTaskResponse,
    OfficeManagerTaskUpdateRequest,
)
from app.hal.storage import (
    get_office_manager_task,
    get_office_manager_task_metrics as get_office_manager_task_metrics_from_storage,
    insert_office_manager_task,
    list_office_manager_tasks as list_office_manager_tasks_from_storage,
    update_office_manager_task as update_office_manager_task_in_storage,
)

VALID_STATUSES = {"open", "in_progress", "blocked", "completed", "dismissed"}
VALID_PRIORITIES = {"low", "normal", "high", "urgent"}
VALID_CATEGORIES = {
    "claim",
    "patient_prep",
    "documentation",
    "treatment_plan",
    "hygiene_recall",
    "compliance",
    "vendor",
    "report",
    "other",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_response(payload: dict[str, object]) -> OfficeManagerTaskResponse:
    return OfficeManagerTaskResponse.model_validate(payload)


def create_office_manager_task(
    request: OfficeManagerTaskCreateRequest,
    *,
    actor: str,
    roles: list[str],
) -> OfficeManagerTaskResponse:
    now = _utc_now()
    task_id = f"omt-{uuid4().hex[:12]}"
    payload = {
        "task_id": task_id,
        "title": request.title.strip(),
        "description": request.description.strip(),
        "category": request.category,
        "status": "open",
        "priority": request.priority,
        "patient_label": request.patient_label,
        "claim_id": request.claim_id,
        "source_refs": list(request.source_refs),
        "missing_data_codes": list(request.missing_data_codes),
        "due_date": request.due_date,
        "assigned_to": request.assigned_to,
        "created_by": actor,
        "created_at_utc": now,
        "updated_at_utc": now,
        "local_only": True,
        "external_action_performed": False,
        "softdent_writeback_performed": False,
    }
    insert_office_manager_task(payload)
    record_office_manager_task_audit(
        task_id=task_id,
        actor=actor,
        roles_used=roles,
        action="created",
        status="open",
        title=payload["title"],
        category=str(payload["category"]),
    )
    return _to_response(payload)


def list_office_manager_tasks(*, limit: int = 25, status: str | None = None) -> dict[str, object]:
    items, total_count = list_office_manager_tasks_from_storage(limit=limit, status=status)
    return {
        "items": [_to_response(item).model_dump() for item in items],
        "total_count": total_count,
        "local_only": True,
        "external_action_performed": False,
        "softdent_writeback_performed": False,
        "submission_status": "not_submitted",
    }


def update_office_manager_task(
    task_id: str,
    request: OfficeManagerTaskUpdateRequest,
    *,
    actor: str,
    roles: list[str],
) -> OfficeManagerTaskResponse:
    existing = get_office_manager_task(task_id)
    if existing is None:
        raise LookupError(f"Office manager task '{task_id}' was not found.")

    updates: dict[str, object] = {}
    if request.title is not None:
        updates["title"] = request.title.strip()
    if request.description is not None:
        updates["description"] = request.description.strip()
    if request.category is not None:
        if request.category not in VALID_CATEGORIES:
            raise ValueError(f"Unsupported task category: {request.category}")
        updates["category"] = request.category
    if request.status is not None:
        if request.status not in VALID_STATUSES:
            raise ValueError(f"Unsupported task status: {request.status}")
        updates["status"] = request.status
    if request.priority is not None:
        if request.priority not in VALID_PRIORITIES:
            raise ValueError(f"Unsupported task priority: {request.priority}")
        updates["priority"] = request.priority
    if request.patient_label is not None:
        updates["patient_label"] = request.patient_label
    if request.claim_id is not None:
        updates["claim_id"] = request.claim_id
    if request.source_refs is not None:
        updates["source_refs"] = list(request.source_refs)
    if request.missing_data_codes is not None:
        updates["missing_data_codes"] = list(request.missing_data_codes)
    if request.due_date is not None:
        updates["due_date"] = request.due_date
    if request.assigned_to is not None:
        updates["assigned_to"] = request.assigned_to

    if not updates:
        raise ValueError("At least one task field must be provided for update.")

    updates["updated_at_utc"] = _utc_now()
    updated = update_office_manager_task_in_storage(task_id, updates)
    if updated is None:
        raise LookupError(f"Office manager task '{task_id}' was not found.")

    record_office_manager_task_audit(
        task_id=task_id,
        actor=actor,
        roles_used=roles,
        action="updated",
        status=str(updated.get("status") or ""),
        title=str(updated.get("title") or ""),
        category=str(updated.get("category") or ""),
    )
    return _to_response(updated)


def get_office_manager_task_metrics() -> dict[str, int]:
    return get_office_manager_task_metrics_from_storage()
