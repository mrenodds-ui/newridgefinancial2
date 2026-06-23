from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator


BRIGHTNESS_INTENT_PATTERN = re.compile(
    r"(?i)(?:set|change|make|lower|raise|increase|decrease|dim|brighten)[^\n\r]{0,40}?brightness[^\n\r]{0,20}?(?:to|at)\s*(\d{1,3})%?"
)


class MonitorStatusOutput(BaseModel):
    source_backend: str = Field(..., description="'ddc_ci' or 'empty'")
    brightness: int | None = Field(None, description="Current luminance level from 0 to 100")
    contrast: int | None = Field(None, description="Current contrast level from 0 to 100")
    input_source: str | None = Field(None, description="Active display input name when available")
    raw_vcp_codes: dict[str, Any] = Field(default_factory=dict, description="Unmapped raw VCP values captured for diagnostics")
    health: dict[str, Any] = Field(
        ...,
        description="Health envelope containing connected boolean and optional error string",
    )


class MonitorMutationIntent(BaseModel):
    action_type: Literal["SET_LUMINANCE"] = Field("SET_LUMINANCE", description="Hardware action token")
    target_value: int = Field(..., description="Requested monitor luminance level from 0 to 100")
    human_review_required: Literal[True] = True
    status: Literal["pending_confirmation"] = "pending_confirmation"

    @field_validator("target_value")
    @classmethod
    def validate_target_value(cls, value: int) -> int:
        if not 0 <= value <= 100:
            raise ValueError("target_value must be between 0 and 100")
        return value


class MonitorMutationExecutionRequest(MonitorMutationIntent):
    user_confirmed: bool = Field(..., description="Explicit human approval gate for hardware mutation")


class MonitorMutationExecutionResult(BaseModel):
    status: Literal["executed", "rejected", "failed"]
    action_type: Literal["SET_LUMINANCE"] | None = None
    requested_value: int | None = None
    applied_value: int | None = None
    error: str | None = None
    source_backend: str = "ddc_ci"


def _coerce_vcp_debug_value(value: object) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def get_monitor_status() -> dict[str, Any]:
    try:
        from monitorcontrol import get_monitors

        monitors = get_monitors()
        if not monitors:
            raise RuntimeError("No physical monitors discovered with DDC/CI capabilities.")

        with monitors[0] as monitor:
            brightness = monitor.get_luminance()
            contrast = monitor.get_contrast()
            raw_input_value: object | None = None

            try:
                raw_input_value = monitor.get_input_source()
                raw_input = str(raw_input_value)
            except Exception:
                raw_input = "Unknown/Unsupported"

            output = MonitorStatusOutput(
                source_backend="ddc_ci",
                brightness=int(brightness) if brightness is not None else None,
                contrast=int(contrast) if contrast is not None else None,
                input_source=raw_input,
                raw_vcp_codes={
                    "input_source_raw": _coerce_vcp_debug_value(raw_input_value),
                    "input_source_raw_type": type(raw_input_value).__name__ if raw_input_value is not None else None,
                },
                health={"connected": True, "error": None},
            )
            return output.model_dump()

    except Exception as exc:
        return MonitorStatusOutput(
            source_backend="empty",
            brightness=None,
            contrast=None,
            input_source=None,
            raw_vcp_codes={},
            health={"connected": False, "error": str(exc)},
        ).model_dump()


def build_monitor_mutation_intent(question: str) -> dict[str, Any] | None:
    lowered = question.lower()
    if "brightness" not in lowered:
        return None

    match = BRIGHTNESS_INTENT_PATTERN.search(question)
    if not match:
        return None

    try:
        intent = MonitorMutationIntent(target_value=int(match.group(1)))
    except (ValueError, ValidationError):
        return None
    return intent.model_dump()