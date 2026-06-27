"""Shared pytest defaults so app startup validation matches local test expectations."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("APP_AUTH_SESSION_SECRET", "unit-test-session-secret-not-for-production")

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _isolate_env_from_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use process env only during tests so a populated workspace .env does not override monkeypatch."""

    import app.ai_local_config as ai_local_config
    import app.config_runtime as config_runtime

    def _test_env_setting(name: str, default: str = "") -> str:
        value = os.getenv(name)
        if value is not None and value != "":
            return value
        return default

    monkeypatch.setattr(config_runtime, "get_env_setting", _test_env_setting)
    monkeypatch.setattr(ai_local_config, "get_env_setting", _test_env_setting)


@pytest.fixture
def canonical_softdent_dashboard(monkeypatch):
    """Pin SoftDent dashboard rows to a committed deterministic fixture.

    The live import directory (``app/data/imports/softdent``) is mutable and can be
    rewritten by other tests in the same session (e.g. SoftDent import / route smoke
    checks). Tests that assert exact aggregate facts must read this canonical fixture
    instead of the shared on-disk snapshot so they stay deterministic regardless of
    test ordering. This does not introduce synthetic A/R, demo KPIs, or fake totals;
    it mirrors the canonical dashboard snapshot only.
    """

    import app.services as services

    rows = json.loads(
        (_FIXTURES_DIR / "softdent_dashboard_canonical.json").read_text(encoding="utf-8")
    )
    monkeypatch.setattr(services, "load_softdent_dashboard_rows", lambda: [dict(row) for row in rows])
    return rows
