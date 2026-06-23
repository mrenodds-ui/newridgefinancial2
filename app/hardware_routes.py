from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import ValidationError

from .auth import AuthenticatedUser, require_roles
from .hal.hardware_tools import MonitorMutationExecutionRequest, MonitorMutationExecutionResult


router = APIRouter()


def handle_authenticated_hardware_execution(request_payload: dict[str, Any]) -> dict[str, Any]:
    try:
        validated_request = MonitorMutationExecutionRequest.model_validate(request_payload)
    except ValidationError as exc:
        return MonitorMutationExecutionResult(
            status="failed",
            action_type=request_payload.get("action_type") if isinstance(request_payload.get("action_type"), str) else None,
            requested_value=request_payload.get("target_value") if isinstance(request_payload.get("target_value"), int) else None,
            applied_value=None,
            error=f"Execution request validation failed: {exc.errors()[0]['msg']}",
        ).model_dump()

    if not validated_request.user_confirmed:
        return MonitorMutationExecutionResult(
            status="rejected",
            action_type=validated_request.action_type,
            requested_value=validated_request.target_value,
            applied_value=None,
            error="Human-in-the-loop confirmation flag was false.",
        ).model_dump()

    try:
        from monitorcontrol import get_monitors

        monitors = get_monitors()
        if not monitors:
            raise RuntimeError("No physical displays detected with DDC/CI capability at runtime.")

        with monitors[0] as monitor:
            monitor.set_luminance(validated_request.target_value)

        return MonitorMutationExecutionResult(
            status="executed",
            action_type=validated_request.action_type,
            requested_value=validated_request.target_value,
            applied_value=validated_request.target_value,
            error=None,
        ).model_dump()
    except Exception as exc:
        return MonitorMutationExecutionResult(
            status="failed",
            action_type=validated_request.action_type,
            requested_value=validated_request.target_value,
            applied_value=None,
            error=f"Execution pipeline block fault: {exc}",
        ).model_dump()


@router.post("/api/hardware/monitor-actions", response_model=MonitorMutationExecutionResult, tags=["Hardware"], include_in_schema=False)
@router.post("/hardware/monitor-actions", response_model=MonitorMutationExecutionResult, tags=["Hardware"])
def execute_monitor_action(
    payload: dict[str, Any],
    user: AuthenticatedUser = Depends(require_roles("admin")),
):
    del user
    return handle_authenticated_hardware_execution(payload)
