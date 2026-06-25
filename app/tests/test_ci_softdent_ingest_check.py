from __future__ import annotations

import json
import os

_MIN_AUTH_USERS_JSON = json.dumps(
    [
        {
            "username": "admin",
            "display_name": "Administrator",
            "password": "password",
            "roles": ["dashboard:read", "hal:operator", "hal:index:refresh", "admin"],
        }
    ]
)
os.environ.setdefault("APP_AUTH_USERS_JSON", _MIN_AUTH_USERS_JSON)

from app.auth import clear_user_registry_cache
from scripts.focused_new_file_ingest_check import main as run_softdent_ingest_check


def test_ci_softdent_ingest_check():
    # The ingest check enters ``with TestClient(app):`` which runs app startup
    # auth validation. Other test modules in a shared session set
    # ``APP_AUTH_USERS_JSON`` to narrower role sets, so the module-level
    # ``setdefault`` above can be a no-op by the time this test runs. Force the
    # full required-role auth users for this check (test-only credentials, not a
    # production security change) and restore the prior value afterwards.
    original_users_json = os.environ.get("APP_AUTH_USERS_JSON")
    os.environ["APP_AUTH_USERS_JSON"] = _MIN_AUTH_USERS_JSON
    clear_user_registry_cache()
    try:
        exit_code = run_softdent_ingest_check()
    finally:
        if original_users_json is None:
            os.environ.pop("APP_AUTH_USERS_JSON", None)
        else:
            os.environ["APP_AUTH_USERS_JSON"] = original_users_json
        clear_user_registry_cache()
    assert exit_code == 0, "scripts/focused_new_file_ingest_check.py reported ingest check failures"
