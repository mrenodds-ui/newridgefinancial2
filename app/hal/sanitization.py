from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class SanitizationFinding:
    label: str
    replacement: str


NAME_AFTER_PATIENT_PATTERN = re.compile(
    r"\b((?i:patient)\s+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b"
)

SANITIZATION_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("date", re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"), "DATE_REDACTED"),
    (
        "phone",
        re.compile(r"\b(?:\+1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        "PHONE_REDACTED",
    ),
    ("mrn", re.compile(r"(?i)\bmrn\s*[:#-]?\s*[a-z0-9-]+\b"), "MRN_REDACTED"),
    (
        "account",
        re.compile(r"(?i)\b(?:account|acct|chart)\s*[:#-]?\s*[a-z0-9-]+\b"),
        "ACCOUNT_REDACTED",
    ),
    ("email", re.compile(r"\b[\w.%-]+@[\w.-]+\.[A-Za-z]{2,}\b"), "EMAIL_REDACTED"),
)


def sanitize_hal_text(text: str) -> dict[str, object]:
    sanitized_text = text.strip()
    findings: list[dict[str, str]] = []

    def replace_patient_name(match: re.Match[str]) -> str:
        findings.append({"label": "patient_name", "replacement": "PATIENT_REDACTED"})
        return f"{match.group(1)}PATIENT_REDACTED"

    sanitized_text, _name_count = NAME_AFTER_PATIENT_PATTERN.subn(replace_patient_name, sanitized_text)

    for label, pattern, replacement in SANITIZATION_RULES:
        sanitized_text, match_count = pattern.subn(replacement, sanitized_text)
        if match_count:
            findings.append({"label": label, "replacement": replacement})

    return {
        "sanitized_text": sanitized_text,
        "findings": findings,
    }