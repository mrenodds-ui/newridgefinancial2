"""RETIRED — NR2 desktop uses NewRidgeFinancial2/import_sync.py instead."""
from __future__ import annotations

import sys

print(
    "RETIRED: refresh_from_softdent_and_verify.py targets the retired FastAPI backend.\n"
    "Use: python NewRidgeFinancial2/import_sync.py",
    file=sys.stderr,
)
raise SystemExit(1)

from contextlib import contextmanager
import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


LOCAL_VERIFY_AUTH_USERS_JSON = json.dumps(
    [
        {
            "username": "local-hal-operator",
            "password": "local-hal-operator-pass",
            "display_name": "Local HAL Operator",
            "roles": ["dashboard:read", "hal:operator", "hal:index:refresh", "admin"],
        }
    ]
)


if not os.environ.get("APP_AUTH_USERS_JSON", "").strip():
    os.environ["APP_AUTH_USERS_JSON"] = LOCAL_VERIFY_AUTH_USERS_JSON

from app.main import app  # noqa: E402
from app.auth import authenticate, get_service_user  # noqa: E402
from app.data_pipeline import recompute_cache  # noqa: E402


@contextmanager
def _service_test_client(*, required_role: str):
    service_user = get_service_user(required_role)
    existing_override = app.dependency_overrides.get(authenticate)
    app.dependency_overrides[authenticate] = lambda: service_user
    try:
        with TestClient(app) as client:
            yield client
    finally:
        if existing_override is None:
            app.dependency_overrides.pop(authenticate, None)
        else:
            app.dependency_overrides[authenticate] = existing_override


def _coerce_pull_status_sections(payload: object) -> tuple[object | None, object | None, dict[str, object]]:
    if not isinstance(payload, dict):
        return None, None, {}

    raw_status = payload.get("status")
    if isinstance(raw_status, dict):
        return payload.get("daily_refresh_enabled"), payload.get("last_refresh_date"), raw_status
    return payload.get("daily_refresh_enabled"), payload.get("last_refresh_date"), {}


def main() -> int:
    checks: list[dict] = []
    failures: list[dict] = []
    default_headers = {"host": "127.0.0.1"}

    page_paths = [
        "/",
        "/admin",
        "/softdent",
        "/quickbooks",
        "/accounts-receivable",
        "/reconciliation",
        "/trends",
        "/ebitda",
        "/claims",
        "/hal9000",
        "/reports",
    ]

    api_paths = [
        "/api/health",
        "/api/kpis",
        "/api/admin",
        "/api/reconciliation",
        "/api/hal9000/phases",
        "/api/reports/pull-status",
        "/api/reports/practice-central-delta",
    ]

    with _service_test_client(required_role="admin") as client:
        # Force immediate refresh from configured sources (including SoftDent auto-pull)
        # after startup hooks initialize app.state settings and caches.
        recompute_cache(app)

        for path in page_paths + api_paths:
            response = client.get(path, headers=default_headers)
            checks.append({"method": "GET", "path": path, "status": response.status_code})
            if response.status_code >= 400:
                failures.append(
                    {
                        "method": "GET",
                        "path": path,
                        "status": response.status_code,
                        "body": response.text[:300],
                    }
                )

        pull_status = client.get("/api/reports/pull-status", headers=default_headers).json()
        kpis_payload = client.get("/api/kpis", headers=default_headers).json()
        claims_page = client.get("/claims", headers=default_headers)

    daily_refresh_enabled, last_refresh_date, status_sections = _coerce_pull_status_sections(pull_status)

    summary = {
        "checked": checks,
        "failures": failures,
        "refresh": {
            "daily_refresh_enabled": daily_refresh_enabled,
            "last_refresh_date": last_refresh_date,
            "softdent_pull": status_sections.get("softdent", {}),
            "quickbooks_pull": status_sections.get("quickbooks", {}),
            "practice_central_pull": status_sections.get("practice_central", {}),
            "kpi_rows": len(kpis_payload.get("items") or []),
            "claims_page_status": claims_page.status_code,
        },
    }

    print(json.dumps(summary, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
