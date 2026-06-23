from __future__ import annotations

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

from app.main import app  # noqa: E402
from app.auth import authenticate, get_service_user  # noqa: E402


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


def main() -> int:
    failures: list[dict] = []
    checked: list[dict] = []
    default_headers = {"host": "127.0.0.1"}
    expected_get_status_overrides = {
        "/quickbooks/odbc/csv": {422},
        "/quickbooks/odbc": {422},
        "/api/quickbooks/odbc/csv": {422},
        "/api/quickbooks/odbc": {422},
        "/api/hal9000/chart-files": {422},
        "/api/api/hal9000/chart-files": {422},
    }

    with _service_test_client(required_role="admin") as client:
        for route in app.routes:
            methods = getattr(route, "methods", set()) or set()
            path = getattr(route, "path", "")
            if "GET" not in methods:
                continue
            if not path or "{" in path:
                continue
            if path.startswith("/docs") or path.startswith("/redoc") or path.startswith("/openapi"):
                continue

            try:
                response = client.get(path, headers=default_headers)
                checked.append({"method": "GET", "path": path, "status": response.status_code})
                expected_statuses = expected_get_status_overrides.get(path)
                if expected_statuses is not None:
                    if response.status_code not in expected_statuses:
                        failures.append(
                            {
                                "method": "GET",
                                "path": path,
                                "status": response.status_code,
                                "expected": sorted(expected_statuses),
                                "body": response.text[:300],
                            }
                        )
                elif response.status_code >= 400:
                    failures.append(
                        {
                            "method": "GET",
                            "path": path,
                            "status": response.status_code,
                            "body": response.text[:300],
                        }
                    )
            except Exception as exc:  # pragma: no cover - smoke utility
                failures.append({"method": "GET", "path": path, "error": str(exc)})

        post_smoke_cases = [
            {
                "path": "/softdent/import",
                "kwargs": {
                    "files": {
                        "file": (
                            "smoke_softdent.csv",
                            b"Month,Metric,Amount\\n2026-01,Production,100\\n",
                            "text/csv",
                        )
                    }
                },
            },
            {
                "path": "/quickbooks/import",
                "kwargs": {
                    "files": {
                        "file": (
                            "smoke_quickbooks.csv",
                            b"Date,Account,Category,Amount\\n2026-01-01,Income,Income,100\\n",
                            "text/csv",
                        )
                    }
                },
            },
            {
                "path": "/hal9000",
                "kwargs": {"json": {"question": "status"}},
            },
        ]

        for case in post_smoke_cases:
            path = case["path"]
            try:
                response = client.post(
                    path,
                    follow_redirects=False,
                    headers=default_headers,
                    **case["kwargs"],
                )
                checked.append({"method": "POST", "path": path, "status": response.status_code})
                if response.status_code >= 400:
                    failures.append(
                        {
                            "method": "POST",
                            "path": path,
                            "status": response.status_code,
                            "body": response.text[:300],
                        }
                    )
            except Exception as exc:  # pragma: no cover - smoke utility
                failures.append({"method": "POST", "path": path, "error": str(exc)})

    print(f"checked={len(checked)} failures={len(failures)}")
    print(json.dumps({"checked": checked, "failures": failures}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
