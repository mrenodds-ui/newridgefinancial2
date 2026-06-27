from __future__ import annotations

from app.hal.employee_context import (
    employee_context_limits,
    hal_employee_raw_context_enabled,
    prepare_employee_context_text,
)


def test_raw_employee_context_enabled_for_hal_operator_by_default(monkeypatch):
    monkeypatch.delenv("HAL_EMPLOYEE_RAW_CONTEXT", raising=False)

    assert hal_employee_raw_context_enabled(["hal:operator"]) is True
    assert hal_employee_raw_context_enabled(["dashboard:read"]) is False


def test_raw_employee_context_can_be_disabled(monkeypatch):
    monkeypatch.setenv("HAL_EMPLOYEE_RAW_CONTEXT", "0")

    assert hal_employee_raw_context_enabled(["hal:operator"]) is False


def test_employee_context_text_sanitizes_unless_raw_enabled():
    text = "Patient Jane Roe has MRN 12345 and phone 555-123-4567."

    sanitized = prepare_employee_context_text(text, raw_employee_context=False)
    raw = prepare_employee_context_text(text, raw_employee_context=True)

    assert "Patient PATIENT_REDACTED" in sanitized
    assert "MRN_REDACTED" in sanitized
    assert "PHONE_REDACTED" in sanitized
    assert raw == text


def test_employee_context_limits_expand_only_for_raw_context():
    sanitized = employee_context_limits(raw_employee_context=False)
    raw = employee_context_limits(raw_employee_context=True)

    assert raw["context_limit"] > sanitized["context_limit"]
    assert raw["excerpt_char_limit"] > sanitized["excerpt_char_limit"]
    assert raw["clinical_note_max_length"] > sanitized["clinical_note_max_length"]
