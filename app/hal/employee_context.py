from __future__ import annotations

import os
from typing import Iterable

from .sanitization import sanitize_hal_text

HAL_EMPLOYEE_RAW_CONTEXT_ENV = "HAL_EMPLOYEE_RAW_CONTEXT"

# Prompt and excerpt bounds when employee raw context is active for hal:operator.
EMPLOYEE_RAW_CONTEXT_LIMIT = 6
EMPLOYEE_RAW_EXCERPT_CHAR_LIMIT = 1200
EMPLOYEE_RAW_SUMMARY_CHAR_LIMIT = 1800
EMPLOYEE_RAW_ANSWER_EXCERPT_LIMIT = 4
EMPLOYEE_RAW_EXPORT_ROW_LIMIT = 5
EMPLOYEE_RAW_EXPORT_FIELD_LIMIT = 12
EMPLOYEE_RAW_CLINICAL_NOTE_MAX_LENGTH = 1200

# Default sanitized bounds mirror the pre-existing conservative retrieval path.
SANITIZED_CONTEXT_LIMIT = 2
SANITIZED_EXCERPT_CHAR_LIMIT = 300
SANITIZED_SUMMARY_CHAR_LIMIT = 600
SANITIZED_ANSWER_EXCERPT_LIMIT = 2
SANITIZED_EXPORT_ROW_LIMIT = 3
SANITIZED_EXPORT_FIELD_LIMIT = 6
SANITIZED_CLINICAL_NOTE_MAX_LENGTH = 500


def hal_employee_raw_context_enabled(roles: Iterable[str] | object | None) -> bool:
    """Whether richer local export excerpts may be used for authorized staff."""
    if os.getenv(HAL_EMPLOYEE_RAW_CONTEXT_ENV, "1").strip().lower() in {"0", "false", "no", "off"}:
        return False
    if roles is None:
        return True
    return "hal:operator" in {str(role) for role in roles}


def prepare_employee_context_text(text: str, *, raw_employee_context: bool) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    if raw_employee_context:
        return cleaned
    return str(sanitize_hal_text(cleaned)["sanitized_text"])


def employee_context_limits(*, raw_employee_context: bool) -> dict[str, int]:
    if raw_employee_context:
        return {
            "context_limit": EMPLOYEE_RAW_CONTEXT_LIMIT,
            "excerpt_char_limit": EMPLOYEE_RAW_EXCERPT_CHAR_LIMIT,
            "summary_char_limit": EMPLOYEE_RAW_SUMMARY_CHAR_LIMIT,
            "answer_excerpt_limit": EMPLOYEE_RAW_ANSWER_EXCERPT_LIMIT,
            "export_row_limit": EMPLOYEE_RAW_EXPORT_ROW_LIMIT,
            "export_field_limit": EMPLOYEE_RAW_EXPORT_FIELD_LIMIT,
            "clinical_note_max_length": EMPLOYEE_RAW_CLINICAL_NOTE_MAX_LENGTH,
        }
    return {
        "context_limit": SANITIZED_CONTEXT_LIMIT,
        "excerpt_char_limit": SANITIZED_EXCERPT_CHAR_LIMIT,
        "summary_char_limit": SANITIZED_SUMMARY_CHAR_LIMIT,
        "answer_excerpt_limit": SANITIZED_ANSWER_EXCERPT_LIMIT,
        "export_row_limit": SANITIZED_EXPORT_ROW_LIMIT,
        "export_field_limit": SANITIZED_EXPORT_FIELD_LIMIT,
        "clinical_note_max_length": SANITIZED_CLINICAL_NOTE_MAX_LENGTH,
    }
