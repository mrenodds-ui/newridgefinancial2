from __future__ import annotations

import json
import os

_MIN_AUTH_USERS_JSON = json.dumps(
    [
        {
            "username": "admin",
            "display_name": "Administrator",
            "password": "password",
            "roles": [
                "dashboard:read",
                "hal:operator",
                "hal:index:refresh",
                "admin",
                "softdent:read",
                "softdent:ledger:read",
            ],
        }
    ]
)
os.environ.setdefault("APP_AUTH_USERS_JSON", _MIN_AUTH_USERS_JSON)

from app.auth import clear_user_registry_cache  # noqa: E402
from scripts.smoke_all_routes import main as run_route_wiring_check  # noqa: E402


def test_ci_route_wiring():
    # Other tests mutate APP_AUTH_USERS_JSON and the cached user registry. Force
    # the route-wiring user set and clear the cache so the admin service user is
    # always resolvable regardless of test execution order.
    os.environ["APP_AUTH_USERS_JSON"] = _MIN_AUTH_USERS_JSON
    clear_user_registry_cache()
    try:
        exit_code = run_route_wiring_check()
        assert exit_code == 0, "scripts/smoke_all_routes.py reported route wiring failures"
    finally:
        clear_user_registry_cache()
