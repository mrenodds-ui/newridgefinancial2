"""Operator consent executor toggle — gates manual sync/ODBC/posting when disabled."""

from __future__ import annotations

import os


def consent_executor_enabled() -> bool:
    return os.environ.get("NR2_CONSENT_EXECUTOR", "1").strip().lower() in {"1", "true", "yes", "on"}
