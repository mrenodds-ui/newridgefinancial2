"""Shared pytest defaults so app startup validation matches local test expectations."""

from __future__ import annotations

import os

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("APP_AUTH_SESSION_SECRET", "unit-test-session-secret-not-for-production")
