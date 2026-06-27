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


@pytest.fixture(autouse=True)
def _isolate_softdent_eod_default_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the operator's real local DAYSHEET drop out of tests.

    ``_default_eod_report_dir`` is always scanned by the End-of-Day A/R resolver, and it
    points at ``app/data/imports/softdent/daily_end_of_day`` where a real (gitignored)
    DAYSHEET report may live. Tests that exercise the missing/stale A/R paths must not pick
    up that real file. This redirects the default scan dir to an empty temp location;
    tests that need a report still set ``SOFTDENT_END_OF_DAY_REPORT_PATH`` explicitly, which
    is honored ahead of the default dir.
    """

    import app.hal.softdent_end_of_day_report as eod_module

    empty_dir = tmp_path / "softdent_eod_default_empty"
    monkeypatch.setattr(eod_module, "_default_eod_report_dir", lambda: empty_dir)


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
