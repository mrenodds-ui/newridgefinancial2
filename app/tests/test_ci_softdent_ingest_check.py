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

from scripts.focused_new_file_ingest_check import main as run_softdent_ingest_check


def test_ci_softdent_ingest_check():
    exit_code = run_softdent_ingest_check()
    assert exit_code == 0, "scripts/focused_new_file_ingest_check.py reported ingest check failures"
