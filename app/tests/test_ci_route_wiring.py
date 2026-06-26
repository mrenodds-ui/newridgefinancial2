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

from scripts.smoke_all_routes import main as run_route_wiring_check


def test_ci_route_wiring():
    exit_code = run_route_wiring_check()
    assert exit_code == 0, "scripts/smoke_all_routes.py reported route wiring failures"
