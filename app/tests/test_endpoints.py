import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
import app.hal.orchestrator as hal_orchestrator
import app.hal.widget_feed as widget_feed_module
import app.hardware_routes as hardware_routes_module
import app.routes as routes_module
import app.services as services_module

from app.auth import clear_user_registry_cache, hash_password, validate_auth_configuration

TEST_AUTH_USERS_JSON = json.dumps(
    [
        {
            "username": "admin",
            "display_name": "Administrator",
            "password": "password",
            "roles": ["dashboard:read", "hal:operator", "hal:index:refresh", "admin"],
        },
        {
            "username": "viewer",
            "display_name": "Viewer",
            "password": "viewer-password",
            "roles": ["dashboard:read"],
        },
        {
            "username": "operator",
            "display_name": "Operator",
            "password": "operator-password",
            "roles": ["hal:operator"],
        }
    ]
)

os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON

from app.main import app

client = TestClient(app)


def setup_function():
    os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON
    runtime_dir = Path(__file__).resolve().parent / ".endpoint_test_runtime" / uuid4().hex
    os.environ["HAL_ALLOWED_BASE_PATH"] = str(runtime_dir)
    os.environ["HAL_SQLITE_PATH"] = str(runtime_dir / "hal_test.sqlite3")
    os.environ["HAL_CHROMA_PATH"] = str(runtime_dir / "hal_chroma")
    clear_user_registry_cache()
    widget_feed_module.configure_widget_feed_cache_path(runtime_dir / "import_widget_feed.json")
    widget_feed_module.clear_widget_feed()

def basic_auth():
    return ("admin", "password")


def viewer_auth():
    return ("viewer", "viewer-password")


def operator_auth():
    return ("operator", "operator-password")


def _fake_hal_financial_sources() -> dict[str, object]:
    fresh_timestamp = datetime.now(timezone.utc).isoformat()

    def softdent_status(excerpt: str) -> dict[str, object]:
        return {
            "available": True,
            "health": "ok",
            "source_backend": "canonical-import",
            "source_file": "softdent_dashboard_data.json",
            "modified_at_utc": fresh_timestamp,
            "checked_at_utc": fresh_timestamp,
            "excerpt": excerpt,
            "confidence_label": "verified",
            "review_required": False,
            "review_flags": [],
        }

    def quickbooks_status(topic: str) -> dict[str, object]:
        return {
            "topic": topic,
            "available": True,
            "health": "ok",
            "source_backend": "sdk",
            "source_id": f"quickbooks-{topic}-summary",
            "source_file": f"quickbooks_{topic}.csv",
            "modified_at_utc": fresh_timestamp,
            "excerpt": f"QuickBooks {topic} summary available.",
            "checked_at_utc": fresh_timestamp,
            "confidence_label": "verified",
            "review_required": False,
            "review_flags": [],
        }

    return {
        "softdent": {
            "available": True,
            "period": "2026-06",
            "provider_count": 4,
            "coverage": {
                "summary": "Missing and limited reports explain why some dashboard charts are unavailable.",
                "counts": {"missing": 7, "limited": 5, "available": 7},
                "rows": [
                    {
                        "key": "trueOutstandingClaims",
                        "label": "True Outstanding Claims",
                        "status": "missing",
                        "summary": "True Outstanding Claims aggregate export is missing from the canonical SoftDent import lane.",
                        "requiredReport": r"outstanding_claims_by_company.csv in C:\SoftDentReportExports",
                        "action": r"Configure the automated SoftDent source pipeline to emit aggregate-only outstanding_claims_by_company.csv into C:\SoftDentReportExports.",
                        "sourceFile": "",
                        "sourceBackend": "missing",
                        "modifiedAtUtc": "",
                        "rowCount": 0,
                        "lastPeriod": "",
                    }
                ],
            },
            "live_snapshot": softdent_status("SoftDent live snapshot available."),
            "live_provider_ranking": softdent_status("SoftDent provider ranking available."),
            "live_payer_mix": softdent_status("SoftDent payer mix available."),
            "live_collection_delta": softdent_status("SoftDent collection delta available."),
            "live_claims": softdent_status("SoftDent claims export available."),
            "live_clinical_notes": softdent_status("SoftDent clinical notes export available."),
        },
        "quickbooks": {
            "sdk": {"available": True, "health": "ok", "checked_at_utc": fresh_timestamp},
            "topics": [],
            "live_revenue": quickbooks_status("revenue"),
            "live_expenses": quickbooks_status("expenses"),
            "live_ar": quickbooks_status("ar"),
        },
    }


def _fake_hal_monitor_status(label: str) -> dict[str, object]:
    fresh_timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "available": True,
        "health": "ok",
        "source_backend": "hal_storage",
        "source_file": f"{label}.sqlite3",
        "modified_at_utc": fresh_timestamp,
        "checked_at_utc": fresh_timestamp,
        "excerpt": f"{label} monitor is current.",
        "review_required": False,
        "review_flags": [],
    }


def _fake_hal_ask_response(answer: str = "ok") -> dict[str, object]:
    return {
        "mode": "local-rag-phase-1",
        "answer": answer,
        "sanitized_question": "What changed?",
        "sanitization_findings": [],
        "retrieved_context": [],
        "guardrails": [],
        "audit_id": "audit-test-1",
        "access_policy": {
            "mode": "local-rag-phase-1",
            "auth_requirement": "authenticated",
            "network_boundary": "local-only",
            "audited": True,
            "workspace_root": "",
            "activity_log_path": "",
            "review_plan_directory": "",
            "allowed_sources": ["SoftDent", "QuickBooks"],
            "disallowed_actions": ["internet"],
            "capability_hierarchy": [],
        },
        "review_actions": [],
        "voice_profile": {
            "lane": "primary",
            "label": "Primary response",
            "tone": "direct and grounded",
            "style_notes": [],
        },
        "governance_notes": [],
    }


def _sample_widget_update_payload() -> dict[str, object]:
    return {
        "manager": "HAL 9000",
        "run_id": "run-123",
        "generated_at": "2026-06-23T12:10:00Z",
        "widgets": {
            "practice_financial_overview": {
                "title": "Practice Financial Overview",
                "status": "SUCCESS",
                "metrics": {
                    "monthly_revenue": 155000.0,
                    "monthly_net_income": 62000.0,
                    "production_total": 171500.0,
                    "collections_total": 149250.0,
                    "collection_rate": 87.03,
                },
            },
            "accounts_payable_automation": {
                "title": "Accounts Payable Automation",
                "status": "SUCCESS",
                "metrics": {
                    "open_bills_total": 12850.0,
                    "expense_total": 93000.0,
                },
            },
            "smart_claims_and_receivables": {
                "title": "Smart Claims & Receivables",
                "status": "DEGRADED",
                "metrics": {
                    "outstanding_claim_count": 34,
                    "outstanding_claim_amount": 22110.0,
                    "unsubmitted_claim_count": 9,
                    "accounts_receivable_total": 21700.0,
                },
            },
            "care_delivery_performance": {
                "title": "Care Delivery Performance",
                "status": "SUCCESS",
                "metrics": {
                    "provider_count": 7,
                    "patient_count": 642,
                    "patient_balance_total": 9100.0,
                },
            },
        },
        "sources": {
            "quickbooks_online": {"last_status": "SUCCESS"},
            "softdent": {"last_status": "SUCCESS"},
        },
        "jobs": {
            "quickbooks_extract": {"status": "SUCCESS"},
            "softdent_extract": {"status": "SUCCESS"},
            "widget_publish": {"status": "SUCCESS"},
        },
    }

def test_health():
    response = client.get("/health", auth=basic_auth())
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_root():
    response = client.get("/", auth=basic_auth())
    assert response.status_code == 200
    assert "Dental Practice Financial Dashboard" in response.text
    assert response.json()["app_url"] == "/app"


def test_root_redirects_browser_requests_to_frontend_app():
    response = client.get(
        "/",
        auth=basic_auth(),
        headers={"accept": "text/html,application/xhtml+xml"},
        follow_redirects=False,
    )

    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/app"


def test_frontend_app_shell_is_served_from_backend():
    response = client.get("/app")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "New Ridge Financial Browser App" in response.text
    assert 'src="/app/assets/' in response.text


def test_frontend_app_deep_link_falls_back_to_index():
    response = client.get("/app/hal-9000")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "New Ridge Financial Browser App" in response.text


def test_frontend_app_routing_does_not_capture_api_routes():
    response = client.get("/api/health", auth=basic_auth())

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_kpis():
    response = client.get("/kpis", auth=basic_auth())
    assert response.status_code == 200
    assert "kpis" in response.json()


def test_quickbooks_odbc_route_is_mounted(monkeypatch):
    def fake_fetch_quickbooks_data(sql_query: str):
        assert "SELECT 1" in sql_query
        return [{"value": 1}]

    monkeypatch.setattr(routes_module, "fetch_quickbooks_data", fake_fetch_quickbooks_data)

    response = client.get("/quickbooks/odbc", params={"sql": "SELECT 1", "dsn": "Injected DSN"}, auth=basic_auth())

    assert response.status_code == 200
    assert response.json() == {"results": [{"value": 1}]}


def test_quickbooks_odbc_post_route_is_mounted(monkeypatch):
    def fake_fetch_quickbooks_data(sql_query: str):
        assert sql_query == "SELECT 1"
        return [{"value": 1}]

    monkeypatch.setattr(routes_module, "fetch_quickbooks_data", fake_fetch_quickbooks_data)

    response = client.post(
        "/quickbooks/odbc",
        auth=basic_auth(),
        json={"sql": "SELECT 1", "dsn": "QuickBooks Data"},
    )

    assert response.status_code == 200
    assert response.json() == {"results": [{"value": 1}]}


def test_quickbooks_odbc_csv_post_route_is_mounted(monkeypatch):
    def fake_fetch_quickbooks_data(sql_query: str):
        assert sql_query == "SELECT 1"
        return [{"value": 1}]

    monkeypatch.setattr(routes_module, "fetch_quickbooks_data", fake_fetch_quickbooks_data)

    response = client.post(
        "/quickbooks/odbc/csv",
        auth=basic_auth(),
        json={"sql": "SELECT 1"},
    )

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "value" in response.text


def test_quickbooks_odbc_route_requires_admin_role(monkeypatch):
    def fake_fetch_quickbooks_data(sql_query: str):
        raise AssertionError("QuickBooks ODBC diagnostics should not run for non-admin users")

    monkeypatch.setattr(routes_module, "fetch_quickbooks_data", fake_fetch_quickbooks_data)

    response = client.get("/quickbooks/odbc", params={"sql": "SELECT 1"}, auth=("viewer", "viewer-password"))

    assert response.status_code == 403
    assert response.json() == {"detail": "Authenticated user does not have the required role for this HAL operation"}


@pytest.mark.parametrize(
    ("path", "expected_content_type"),
    [
        ("/quickbooks/odbc", "application/json"),
        ("/quickbooks/odbc/csv", "text/csv"),
    ],
)
def test_quickbooks_odbc_routes_return_503_for_backend_failures(monkeypatch, path: str, expected_content_type: str):
    def fake_fetch_quickbooks_data(sql_query: str):
        del sql_query
        raise RuntimeError("driver missing")

    monkeypatch.setattr(routes_module, "fetch_quickbooks_data", fake_fetch_quickbooks_data)

    response = client.get(path, params={"sql": "SELECT 1"}, auth=basic_auth())

    assert response.status_code == 503
    assert expected_content_type in response.headers["content-type"]
    assert "driver missing" not in response.text
    if path.endswith("/csv"):
        assert response.text == "Error: QuickBooks ODBC diagnostic is unavailable.\n"
    else:
        assert response.json() == {"detail": "QuickBooks ODBC diagnostic is unavailable."}


def test_legacy_api_alias_routes_remain_available(monkeypatch):
    def fake_fetch_quickbooks_data(sql_query: str):
        assert sql_query == "SELECT 1"
        return [{"value": 1}]

    def fake_answer_hal_question(*, question: str, actor: str, summary: dict[str, object] | None = None, session_id: str | None = None, roles=None, **kwargs):
        assert question == "What changed?"
        return _fake_hal_ask_response(answer="alias-ok")

    monkeypatch.setattr(routes_module, "fetch_quickbooks_data", fake_fetch_quickbooks_data)
    monkeypatch.setattr(routes_module, "answer_hal_question", fake_answer_hal_question)

    kpis_response = client.get("/api/kpis", auth=basic_auth())
    quickbooks_response = client.get("/api/quickbooks/odbc", params={"sql": "SELECT 1"}, auth=basic_auth())
    hal_response = client.post("/api/hal9000", auth=basic_auth(), json={"question": "What changed?"})

    assert kpis_response.status_code == 200
    assert "kpis" in kpis_response.json()
    assert quickbooks_response.status_code == 200
    assert quickbooks_response.json() == {"results": [{"value": 1}]}
    assert hal_response.status_code == 200
    assert hal_response.json()["answer"] == "alias-ok"


def test_accidental_double_api_routes_are_not_exposed(monkeypatch):
    monkeypatch.setattr(hardware_routes_module, "handle_authenticated_hardware_execution", lambda payload: {"status": "executed", "action_type": "SET_LUMINANCE", "requested_value": 30, "applied_value": 30, "error": None})

    api_health_response = client.get("/api/api/health", auth=basic_auth())
    page_summary_response = client.get("/api/api/hal9000/page-summary", auth=basic_auth())
    hal_response = client.post("/api/api/hal9000", auth=basic_auth(), json={"question": "What changed?"})
    hardware_response = client.post(
        "/api/api/hardware/monitor-actions",
        auth=basic_auth(),
        json={
            "action_type": "SET_LUMINANCE",
            "target_value": 30,
            "human_review_required": True,
            "status": "pending_confirmation",
            "user_confirmed": True,
        },
    )

    assert api_health_response.status_code == 404
    assert page_summary_response.status_code == 404
    assert hal_response.status_code == 404
    assert hardware_response.status_code == 404


@pytest.mark.parametrize(
    ("path", "expected_content_type"),
    [
        ("/quickbooks/odbc", "application/json"),
        ("/quickbooks/odbc/csv", "text/csv"),
    ],
)
def test_quickbooks_odbc_routes_reject_non_select_sql(monkeypatch, path: str, expected_content_type: str):
    def fake_fetch_quickbooks_data(sql_query: str):
        raise AssertionError("QuickBooks ODBC diagnostics should not execute non-read-only SQL")

    monkeypatch.setattr(routes_module, "fetch_quickbooks_data", fake_fetch_quickbooks_data)

    response = client.get(path, params={"sql": "DELETE FROM Customer"}, auth=basic_auth())

    assert response.status_code == 400
    assert expected_content_type in response.headers["content-type"]
    if path.endswith("/csv"):
        assert "read-only SELECT statements" in response.text
    else:
        assert response.json()["detail"] == "QuickBooks diagnostic SQL only allows read-only SELECT statements"


def test_hal_shell_commands_endpoint_lists_registered_commands():
    response = client.get("/api/hal/shell/commands", auth=basic_auth())

    assert response.status_code == 200
    payload = response.json()
    assert payload["playbook_active"] is True
    assert payload["verification_endpoint"] == "/api/hal/shell/commands"
    assert "free-form shell" in payload["blocked_actions"]
    assert "run process-state command" in payload["confirmation_required_actions"]
    command_ids = {item["command_id"] for item in payload["registered_commands"]}
    assert "backend.refresh_and_verify" in command_ids
    assert "npm.root.test" in command_ids
    assert "npm.frontend.test" in command_ids


def test_hal_shell_commands_endpoint_suggests_nearest_registered_command():
    response = client.get(
        "/api/hal/shell/commands",
        params={"command_hint": "backend.refresh_verify"},
        auth=basic_auth(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["suggested_command_id"] == "backend.refresh_and_verify"
    assert payload["suggestion_reason"] == "Nearest registered command ID for the provided hint."


def test_load_package_scripts_filters_unsafe_names(tmp_path):
    package_path = tmp_path / "package.json"
    package_path.write_text(
        json.dumps(
            {
                "scripts": {
                    "test": "vitest run",
                    "check:ci": "biome ci src",
                    "evil && whoami": "echo bad",
                }
            }
        ),
        encoding="utf-8",
    )

    entries = hal_orchestrator._load_package_scripts(
        package_path,
        command_prefix="npm.test",
        working_directory=".",
    )

    command_ids = {entry["command_id"] for entry in entries}
    assert "npm.test.test" in command_ids
    assert "npm.test.check:ci" in command_ids
    assert all("evil && whoami" not in command_id for command_id in command_ids)


def test_hal_autonomy_profile_exposes_four_pillars():
    response = client.get("/api/hal9000/autonomy/profile", auth=basic_auth())

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_loop"]["enabled"] is True
    assert payload["function_calling"]["enabled"] is True
    assert payload["sandbox"]["mode"] == "local_backend_registry_only"
    assert payload["state_management"]["backend"] == "sqlite"
    assert payload["function_calling"]["tool_registry_endpoint"] == "/api/hal/shell/commands"


def test_hal_autonomy_run_persists_and_advances():
    create_response = client.post(
        "/api/hal9000/autonomy/runs",
        auth=basic_auth(),
        json={
            "objective": "Check current HAL status and allowed commands for a local autonomy review.",
            "max_steps": 4,
        },
    )

    assert create_response.status_code == 200
    create_payload = create_response.json()
    assert create_payload["status"] == "queued"
    assert create_payload["activity_count"] == 0
    assert create_payload["next_action"]["tool_name"] == "hal.status"

    run_id = create_payload["run_id"]
    advance_response = client.post(
        f"/api/hal9000/autonomy/runs/{run_id}/advance",
        params={"cycles": 2},
        auth=basic_auth(),
    )

    assert advance_response.status_code == 200
    advance_payload = advance_response.json()
    assert advance_payload["status"] in {"running", "completed"}
    assert advance_payload["activity_count"] == 2
    assert advance_payload["activity"][0]["tool_name"] == "hal.status"
    assert advance_payload["activity"][1]["tool_name"] == "hal.shell_commands"

    get_response = client.get(f"/api/hal9000/autonomy/runs/{run_id}", auth=basic_auth())
    assert get_response.status_code == 200
    get_payload = get_response.json()
    assert get_payload["run_id"] == run_id
    assert get_payload["activity_count"] == 2

    list_response = client.get("/api/hal9000/autonomy/runs", auth=basic_auth())
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["count"] >= 1
    assert any(item["run_id"] == run_id for item in list_payload["items"])


def test_hal_autonomy_run_executes_registered_command(monkeypatch):
    monkeypatch.setitem(
        hal_orchestrator.command_registry._registry,
        "backend.refresh_and_verify",
        lambda: {"workflow": "refresh_and_verify", "ok": True},
    )

    create_response = client.post(
        "/api/hal9000/autonomy/runs",
        auth=basic_auth(),
        json={
            "objective": "Refresh and verify the system using the approved backend workflow.",
            "max_steps": 5,
        },
    )

    assert create_response.status_code == 200
    run_id = create_response.json()["run_id"]

    advance_response = client.post(
        f"/api/hal9000/autonomy/runs/{run_id}/advance",
        params={"cycles": 4},
        auth=basic_auth(),
    )

    assert advance_response.status_code == 200
    payload = advance_response.json()
    assert any(item["tool_name"] == "hal.execute_registered_command" for item in payload["activity"])
    assert any("Executed backend.refresh_and_verify successfully" in item["observation"] for item in payload["activity"])


def test_mcp_tools_list_and_call_registered_command(monkeypatch):
    monkeypatch.setitem(
        hal_orchestrator.command_registry._registry,
        "backend.smoke_tests",
        lambda: {"checked": 3, "failures": []},
    )

    list_response = client.get("/api/v1/mcp/tools", auth=basic_auth())
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert any(item["name"] == "backend.smoke_tests" for item in list_payload["tools"])

    call_response = client.post(
        "/api/v1/mcp/tools/call",
        auth=basic_auth(),
        json={"name": "backend.smoke_tests", "arguments": {}},
    )
    assert call_response.status_code == 200
    call_payload = call_response.json()
    assert call_payload["isError"] is False
    assert "Execution status: success" in call_payload["content"][0]["text"]

def test_admin_page():
    response = client.get("/api/hal9000/admin-summary", auth=basic_auth())
    assert response.status_code == 200
    payload = response.json()
    assert "last_refresh_date" in payload
    assert "report_pull_status" in payload
    assert "priority_summary" in payload


def test_auth_session_returns_authenticated_user_roles():
    response = client.get("/api/auth/session", auth=viewer_auth())

    assert response.status_code == 200
    assert response.json() == {
        "username": "viewer",
        "display_name": "Viewer",
        "roles": ["dashboard:read"],
    }


def test_auth_login_sets_cookie_and_logout_clears_session():
    with TestClient(app) as auth_client:
        login_response = auth_client.post(
            "/api/auth/login",
            json={"username": "viewer", "password": "viewer-password"},
        )

        assert login_response.status_code == 200
        assert login_response.json() == {
            "username": "viewer",
            "display_name": "Viewer",
            "roles": ["dashboard:read"],
        }
        assert "httponly" in login_response.headers["set-cookie"].lower()

        session_response = auth_client.get("/api/auth/session")
        assert session_response.status_code == 200
        assert session_response.json() == {
            "username": "viewer",
            "display_name": "Viewer",
            "roles": ["dashboard:read"],
        }

        logout_response = auth_client.post("/api/auth/logout")
        assert logout_response.status_code == 200
        assert logout_response.json() == {"message": "Signed out"}

        logged_out_session_response = auth_client.get("/api/auth/session")
        assert logged_out_session_response.status_code == 401


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/rebuild"),
        ("post", "/api/refresh"),
        ("post", "/api/ci-gates"),
        ("post", "/api/smoke"),
        ("get", "/api/hal9000/admin-summary"),
        ("post", "/api/hal9000/refresh-financial-sources"),
    ],
)
def test_admin_only_routes_reject_viewer(method: str, path: str):
    response = getattr(client, method)(path, auth=viewer_auth())

    assert response.status_code == 403


def test_reports_pull_status_allows_admin_role(monkeypatch):
    expected_payload = {
        "daily_refresh_enabled": True,
        "last_refresh_date": "2026-06-23",
        "status": {},
    }

    monkeypatch.setattr(routes_module, "get_pull_status_payload", lambda app: expected_payload)

    response = client.get("/api/reports/pull-status", auth=basic_auth())

    assert response.status_code == 200
    assert response.json() == expected_payload


@pytest.mark.parametrize("auth", [viewer_auth(), operator_auth()], ids=["viewer", "operator"])
def test_reports_pull_status_rejects_authenticated_user_without_admin_role(auth, monkeypatch):
    monkeypatch.setattr(
        routes_module,
        "get_pull_status_payload",
        lambda app: pytest.fail("pull-status payload should not be resolved for unauthorized users"),
    )

    response = client.get("/api/reports/pull-status", auth=auth)

    assert response.status_code == 403


def test_reports_pull_status_blocks_unauthenticated_request(monkeypatch):
    monkeypatch.setattr(
        routes_module,
        "get_pull_status_payload",
        lambda app: pytest.fail("pull-status payload should not be resolved for unauthenticated users"),
    )

    response = client.get("/api/reports/pull-status")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Basic"


@pytest.mark.parametrize(
    ("path", "auth"),
    [
        ("/softdent", viewer_auth()),
        ("/quickbooks", viewer_auth()),
        ("/accounts-receivable", viewer_auth()),
        ("/trends", viewer_auth()),
        ("/ebitda", viewer_auth()),
        ("/claims", basic_auth()),
        ("/reconciliation", operator_auth()),
        ("/admin", basic_auth()),
        ("/reports", basic_auth()),
        ("/api/admin", basic_auth()),
        ("/api/reconciliation", operator_auth()),
        ("/api/reports/practice-central-delta", basic_auth()),
    ],
    ids=[
        "softdent-dashboard-read",
        "quickbooks-dashboard-read",
        "accounts-receivable-dashboard-read",
        "trends-dashboard-read",
        "ebitda-dashboard-read",
        "claims-dashboard-and-operator",
        "reconciliation-operator",
        "admin-page-admin",
        "reports-page-admin",
        "api-admin-admin",
        "api-reconciliation-operator",
        "practice-central-delta-admin",
    ],
)
def test_legacy_placeholder_routes_keep_not_implemented_for_allowed_roles(path: str, auth: tuple[str, str]):
    response = client.get(path, auth=auth)

    assert response.status_code == 501


@pytest.mark.parametrize(
    ("path", "auth"),
    [
        ("/softdent", operator_auth()),
        ("/quickbooks", operator_auth()),
        ("/accounts-receivable", operator_auth()),
        ("/trends", operator_auth()),
        ("/ebitda", operator_auth()),
        ("/claims", viewer_auth()),
        ("/claims", operator_auth()),
        ("/reconciliation", viewer_auth()),
        ("/admin", viewer_auth()),
        ("/reports", viewer_auth()),
        ("/api/admin", viewer_auth()),
        ("/api/reconciliation", viewer_auth()),
        ("/api/reports/practice-central-delta", viewer_auth()),
    ],
    ids=[
        "softdent-operator-without-dashboard-read",
        "quickbooks-operator-without-dashboard-read",
        "accounts-receivable-operator-without-dashboard-read",
        "trends-operator-without-dashboard-read",
        "ebitda-operator-without-dashboard-read",
        "claims-viewer-without-operator",
        "claims-operator-without-dashboard-read",
        "reconciliation-viewer-without-operator",
        "admin-page-viewer",
        "reports-page-viewer",
        "api-admin-viewer",
        "api-reconciliation-viewer",
        "practice-central-delta-viewer",
    ],
)
def test_legacy_placeholder_routes_reject_low_privilege_authenticated_users(path: str, auth: tuple[str, str]):
    response = client.get(path, auth=auth)

    assert response.status_code == 403


def test_hal_page_summary_allows_dashboard_read_role(monkeypatch):
    monkeypatch.setattr(
        routes_module,
        "_build_financial_summary_payload",
        lambda: {
            "generatedAt": "2026-06-23T00:00:00Z",
            "healthFlags": [],
            "monthlyKpis": [],
            "trailing12Months": [],
            "calendarYearKpis": [],
            "fourYearMonthlyKpis": [],
            "providerProduction": [],
            "topAdaCodes": [],
        },
    )

    response = client.get("/api/hal9000/page-summary", auth=viewer_auth())

    assert response.status_code == 200


def test_hal_page_summary_rejects_authenticated_user_without_dashboard_read_role(monkeypatch):
    monkeypatch.setattr(
        routes_module,
        "_build_financial_summary_payload",
        lambda: {
            "generatedAt": "2026-06-23T00:00:00Z",
            "healthFlags": [],
            "monthlyKpis": [],
            "trailing12Months": [],
            "calendarYearKpis": [],
            "fourYearMonthlyKpis": [],
            "providerProduction": [],
            "topAdaCodes": [],
        },
    )

    response = client.get("/api/hal9000/page-summary", auth=operator_auth())

    assert response.status_code == 403


def test_hal_page_summary_blocks_unauthenticated_request():
    response = client.get("/api/hal9000/page-summary")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Basic"


def test_hal_page_summary_route_returns_financial_summary_payload(monkeypatch):
    fresh_timestamp = "2026-06-18T13:45:00+00:00"

    monkeypatch.setattr(routes_module, "load_softdent_ar_rows", lambda: [])
    monkeypatch.setattr(routes_module, "_build_softdent_latest_ar_snapshot_from_eod", lambda: None)
    monkeypatch.setattr(
        routes_module,
        "load_softdent_dashboard_rows",
        lambda: [
            {"period": "2026-05", "production": 1000, "collections": 800},
            {"period": "2026-06", "production": 1200, "collections": 900},
            {"period": "2026-06", "production": 300, "collections": 200},
        ],
    )
    monkeypatch.setattr(
        routes_module,
        "build_softdent_snapshot",
        lambda: {
            "available": True,
            "period": "2026-06",
            "provider_count": 1,
            "providers": [],
            "totals": {"production": 2500.0, "collections": 1900.0, "insurance": 900.0, "patient": 1000.0},
        },
    )
    monkeypatch.setattr(routes_module, "get_softdent_source_status", lambda: {"available": True, "modified_at_utc": fresh_timestamp})
    monkeypatch.setattr(routes_module, "get_softdent_claim_source_status", lambda: {"available": True, "source_file": "softdent_claims_export.csv", "source_backend": "csv"})
    monkeypatch.setattr(routes_module, "get_softdent_clinical_note_source_status", lambda: {"available": True, "source_file": "softdent_clinical_notes_data.json", "source_backend": "json"})
    monkeypatch.setattr(routes_module, "get_quickbooks_sdk_status", lambda: {"com_available": True})
    monkeypatch.setattr(routes_module, "get_softdent_coverage_metrics", lambda: {"trueOutstandingClaims": {}, "unsubmittedClaims": {}})

    def fake_fetch_quickbooks_sdk_summary(topic: str):
        if topic == "revenue":
            return [{"TotalIncome": 2000.0}]
        if topic == "expenses":
            return [{"TotalExpense": 1500.0}]
        return [{"AccountsReceivable": 300.0}]

    monkeypatch.setattr(routes_module, "fetch_quickbooks_sdk_summary", fake_fetch_quickbooks_sdk_summary)
    monkeypatch.setattr(
        routes_module,
        "load_quickbooks_export_rows",
        lambda topic: [
            {"expense_category": "Dental Supplies", "account_name": "Dental Supplies", "amount": 700.0, "transaction_date": "2026-06-01", "year_month": "2026-06"},
            {"expense_category": "Payroll", "account_name": "Payroll", "amount": 500.0, "transaction_date": "2026-06-10", "year_month": "2026-06"},
            {"expense_category": "Dental Supplies", "account_name": "Dental Supplies", "amount": 300.0, "transaction_date": "2026-05-15", "year_month": "2026-05"},
        ]
        if topic == "expenses"
        else [
            {
                "as_of_date": "2026-06-18",
                "total_ar": 300.0,
                "insurance_ar": 180.0,
                "patient_ar": 120.0,
                "current_balance": 150.0,
                "balance_30": 100.0,
                "balance_60": 50.0,
                "balance_90": 0.0,
                "credit_balance": 0.0,
            }
        ]
        if topic == "ar"
        else [],
    )
    monkeypatch.setattr(
        routes_module,
        "get_financial_source_status",
        lambda: {
            "softdent": {
                "available": True,
                "period": "2026-06",
                "provider_count": 1,
                "coverage": {
                    "summary": "Missing and limited reports explain why some dashboard charts are unavailable.",
                    "counts": {"missing": 7, "limited": 5, "available": 7},
                    "rows": [
                        {
                            "key": "trueOutstandingClaims",
                            "label": "True Outstanding Claims",
                            "status": "missing",
                            "summary": "True Outstanding Claims aggregate export is missing from the canonical SoftDent import lane.",
                            "requiredReport": r"outstanding_claims_by_company.csv in C:\SoftDentReportExports",
                            "action": r"Configure the automated SoftDent source pipeline to emit aggregate-only outstanding_claims_by_company.csv into C:\SoftDentReportExports.",
                            "sourceFile": "",
                            "sourceBackend": "missing",
                            "modifiedAtUtc": "",
                            "rowCount": 0,
                            "lastPeriod": "",
                        }
                    ],
                },
                "live_snapshot": {"available": True, "checked_at_utc": fresh_timestamp, "confidence_label": "verified", "review_required": False, "review_flags": [], "excerpt": "SoftDent live snapshot available."},
                "live_claims": {"available": True, "checked_at_utc": fresh_timestamp, "confidence_label": "verified", "review_required": False, "review_flags": [], "excerpt": "SoftDent claims export available."},
            },
            "quickbooks": {
                "live_revenue": {"available": True, "modified_at_utc": fresh_timestamp, "checked_at_utc": fresh_timestamp, "confidence_label": "verified", "review_required": False, "review_flags": [], "excerpt": "QuickBooks revenue available."},
                "live_expenses": {"available": True, "modified_at_utc": fresh_timestamp, "checked_at_utc": fresh_timestamp, "confidence_label": "verified", "review_required": False, "review_flags": [], "excerpt": "QuickBooks expenses available."},
                "live_ar": {"available": True, "modified_at_utc": fresh_timestamp, "checked_at_utc": fresh_timestamp, "confidence_label": "verified", "review_required": False, "review_flags": [], "excerpt": "QuickBooks A/R available."},
            },
        },
    )

    response = client.get("/api/hal9000/page-summary", auth=basic_auth())

    assert response.status_code == 200
    payload = response.json()
    assert "generatedAt" in payload
    assert "monthlyKpis" in payload
    assert "sourceReview" in payload
    assert payload["softDentCoverage"]["counts"] == {"missing": 7, "limited": 5, "available": 7}
    assert "softDentCoverageMetrics" in payload
    assert payload["claimsSummary"]["available"] is False
    # Unavailable claims summary must not surface misleading $0 amounts; the
    # null amounts are excluded by response_model_exclude_none.
    assert payload["claimsSummary"].get("true_outstanding_claims_amount") is None
    assert payload["claimsSummary"].get("unsubmitted_claims_amount") is None
    assert "quickBooksStatus" in payload
    assert payload["quickBooksStatus"]["lastImportedAtUtc"] == fresh_timestamp
    assert payload["quickBooksProfitLossSummary"][0]["last_imported_at_utc"] == fresh_timestamp
    assert payload["monthlyKpis"] == [
        {
            "year_month": "2026-05",
            "month": "2026-05",
            "gross_production": 1000.0,
            "net_production": 1000.0,
            "collections": 800.0,
            "collection_rate": 80.0,
        },
        {
            "year_month": "2026-06",
            "month": "2026-06",
            "gross_production": 1500.0,
            "net_production": 1500.0,
            "collections": 1100.0,
            "collection_rate": 73.33,
        },
    ]
    assert [item["year_month"] for item in payload["monthlyKpis"]] == sorted(item["year_month"] for item in payload["monthlyKpis"])
    assert payload["currentMonthProduction"] == payload["monthlyKpis"][-1]
    assert payload["currentMonthProduction"]["gross_production"] == 1500.0
    assert payload["currentYearProduction"]["gross_production"] == 2500.0
    assert payload["currentYearProduction"]["collections"] == 1900.0
    assert payload["quickBooksExpenseCategories"][0]["expense_category"] == "Dental Supplies"
    assert payload["quickBooksMonthlyExpenses"] == [
        {
            "year_month": "2026-05",
            "expense_total": 300.0,
            "transaction_count": 1,
            "last_imported_at_utc": fresh_timestamp,
        },
        {
            "year_month": "2026-06",
            "expense_total": 1200.0,
            "transaction_count": 2,
            "last_imported_at_utc": fresh_timestamp,
        },
    ]
    assert payload.get("latestAr") is None


def test_hal_page_summary_uses_softdent_ar_export_when_available(monkeypatch):
    fresh_timestamp = "2026-06-18T13:45:00+00:00"
    monkeypatch.setattr(routes_module, "load_softdent_dashboard_rows", lambda: [])
    monkeypatch.setattr(
        routes_module,
        "load_softdent_ar_rows",
        lambda: [
            {
                "as_of_date": "2026-06-18",
                "total_ar": 21700.0,
                "patient_ar": 9100.0,
                "insurance_ar": 12600.0,
                "current_balance": 12000.0,
                "balance_30": 5000.0,
                "balance_60": 3000.0,
                "balance_90": 1700.0,
                "credit_balance": 0.0,
            }
        ],
    )
    monkeypatch.setattr(
        routes_module,
        "build_softdent_snapshot",
        lambda: {"available": True, "period": "2026-06", "provider_count": 1, "providers": [], "totals": {}},
    )
    monkeypatch.setattr(routes_module, "get_softdent_source_status", lambda: {"available": True, "modified_at_utc": fresh_timestamp})
    monkeypatch.setattr(routes_module, "get_softdent_claim_source_status", lambda: {"available": False})
    monkeypatch.setattr(routes_module, "get_softdent_clinical_note_source_status", lambda: {"available": False})
    monkeypatch.setattr(routes_module, "get_quickbooks_sdk_status", lambda: {"com_available": True})
    monkeypatch.setattr(routes_module, "get_softdent_coverage_metrics", lambda: {"trueOutstandingClaims": {}, "unsubmittedClaims": {}})
    monkeypatch.setattr(routes_module, "fetch_quickbooks_sdk_summary", lambda topic: [{"AccountsReceivable": 99999.0}] if topic == "ar" else [])
    monkeypatch.setattr(routes_module, "load_quickbooks_export_rows", lambda topic: [])
    monkeypatch.setattr(
        routes_module,
        "get_financial_source_status",
        lambda: {
            "softdent": {
                "available": True,
                "coverage": {"summary": "SoftDent coverage available.", "counts": {"missing": 0, "limited": 0, "available": 1}, "rows": []},
                "live_snapshot": {"available": True, "checked_at_utc": fresh_timestamp, "confidence_label": "verified", "review_required": False, "review_flags": [], "excerpt": "SoftDent live snapshot available."},
                "live_claims": {"available": False, "checked_at_utc": fresh_timestamp, "confidence_label": "manual review", "review_required": True, "review_flags": [], "excerpt": "SoftDent claims export unavailable."},
            },
            "quickbooks": {"live_revenue": {}, "live_expenses": {}, "live_ar": {"available": True, "excerpt": "QuickBooks A/R available."}},
        },
    )

    response = client.get("/api/hal9000/page-summary", auth=basic_auth())
    payload = response.json()

    assert response.status_code == 200
    assert payload["latestAr"] == {
        "as_of_date": "2026-06-18",
        "total_ar": 21700.0,
        "insurance_ar": 12600.0,
        "patient_ar": 9100.0,
        "current_balance": 12000.0,
        "balance_30": 5000.0,
        "balance_60": 3000.0,
        "balance_90": 1700.0,
        "credit_balance": 0.0,
        "available": True,
        "source": "softdent",
    }


def test_hal_page_summary_uses_daysheet_eod_ar_when_ar_export_missing(monkeypatch):
    fresh_timestamp = "2026-06-25T13:45:00+00:00"
    monkeypatch.setattr(routes_module, "load_softdent_dashboard_rows", lambda: [])
    monkeypatch.setattr(routes_module, "load_softdent_ar_rows", lambda: [])
    monkeypatch.setattr(
        routes_module,
        "_build_softdent_latest_ar_snapshot_from_eod",
        lambda: {
            "as_of_date": "2026-06-25",
            "total_ar": 73143.91,
            "insurance_ar": 0.0,
            "patient_ar": 0.0,
            "current_balance": 0.0,
            "balance_30": 0.0,
            "balance_60": 0.0,
            "balance_90": 0.0,
            "credit_balance": 0.0,
            "available": True,
            "source": "softdent",
        },
    )
    monkeypatch.setattr(
        routes_module,
        "build_softdent_snapshot",
        lambda: {"available": True, "period": "2026-06", "provider_count": 1, "providers": [], "totals": {}},
    )
    monkeypatch.setattr(routes_module, "get_softdent_source_status", lambda: {"available": True, "modified_at_utc": fresh_timestamp})
    monkeypatch.setattr(routes_module, "get_softdent_claim_source_status", lambda: {"available": False})
    monkeypatch.setattr(routes_module, "get_softdent_clinical_note_source_status", lambda: {"available": False})
    monkeypatch.setattr(routes_module, "get_quickbooks_sdk_status", lambda: {"com_available": True})
    monkeypatch.setattr(routes_module, "get_softdent_coverage_metrics", lambda: {"trueOutstandingClaims": {}, "unsubmittedClaims": {}})
    monkeypatch.setattr(routes_module, "fetch_quickbooks_sdk_summary", lambda topic: [])
    monkeypatch.setattr(routes_module, "load_quickbooks_export_rows", lambda topic: [])
    monkeypatch.setattr(
        routes_module,
        "get_financial_source_status",
        lambda: {
            "softdent": {
                "available": True,
                "coverage": {"summary": "SoftDent coverage available.", "counts": {"missing": 0, "limited": 0, "available": 1}, "rows": []},
                "live_snapshot": {"available": True, "checked_at_utc": fresh_timestamp, "confidence_label": "verified", "review_required": False, "review_flags": [], "excerpt": "SoftDent live snapshot available."},
                "live_claims": {"available": False, "checked_at_utc": fresh_timestamp, "confidence_label": "manual review", "review_required": True, "review_flags": [], "excerpt": "SoftDent claims export unavailable."},
            },
            "quickbooks": {"live_revenue": {}, "live_expenses": {}, "live_ar": {}},
        },
    )

    response = client.get("/api/hal9000/page-summary", auth=basic_auth())
    payload = response.json()

    assert response.status_code == 200
    assert payload["latestAr"] == {
        "as_of_date": "2026-06-25",
        "total_ar": 73143.91,
        "insurance_ar": 0.0,
        "patient_ar": 0.0,
        "current_balance": 0.0,
        "balance_30": 0.0,
        "balance_60": 0.0,
        "balance_90": 0.0,
        "credit_balance": 0.0,
        "available": True,
        "source": "softdent",
    }


def test_widget_update_route_accepts_local_payload_and_surfaces_widget_feed(monkeypatch):
    monkeypatch.delenv("WIDGET_API_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setattr(
        routes_module,
        "_build_financial_summary_payload",
        lambda: {
            "generatedAt": "2026-06-23T00:00:00Z",
            "healthFlags": [],
            "monthlyKpis": [],
            "trailing12Months": [],
            "calendarYearKpis": [],
            "fourYearMonthlyKpis": [],
            "providerProduction": [],
            "topAdaCodes": [],
        },
    )

    update_response = client.post("/api/widgets/update", json=_sample_widget_update_payload())

    assert update_response.status_code == 202
    update_payload = update_response.json()
    assert update_payload["accepted"] is True
    assert update_payload["auth_mode"] == "local"
    assert update_payload["widget_count"] == 4

    response = client.get("/api/hal9000/page-summary", auth=viewer_auth())

    assert response.status_code == 200
    payload = response.json()
    assert payload["widgetFeed"]["manager"] == "HAL 9000"
    assert payload["widgetFeed"]["run_id"] == "run-123"
    assert payload["widgetFeed"]["widgets"]["practice_financial_overview"]["metrics"]["monthly_revenue"] == 155000.0


def test_widget_update_downgrades_receivables_success_without_ar_availability(monkeypatch):
    monkeypatch.delenv("WIDGET_API_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setattr(
        routes_module,
        "_build_financial_summary_payload",
        lambda: {
            "generatedAt": "2026-06-23T00:00:00Z",
            "healthFlags": [],
            "monthlyKpis": [],
            "trailing12Months": [],
            "calendarYearKpis": [],
            "fourYearMonthlyKpis": [],
            "providerProduction": [],
            "topAdaCodes": [],
            "latestAr": None,
        },
    )

    payload = _sample_widget_update_payload()
    payload["widgets"]["smart_claims_and_receivables"]["status"] = "SUCCESS"
    payload["widgets"]["care_delivery_performance"]["status"] = "SUCCESS"

    update_response = client.post("/api/widgets/update", json=payload)

    assert update_response.status_code == 202
    feed = widget_feed_module.get_widget_feed()
    assert feed is not None
    claims_widget = feed["widgets"]["smart_claims_and_receivables"]
    care_widget = feed["widgets"]["care_delivery_performance"]
    assert claims_widget["status"] == "DEGRADED"
    assert claims_widget["metrics"]["accounts_receivable_total"] is None
    assert claims_widget["metrics"]["outstanding_claim_amount"] == 22110.0
    assert care_widget["status"] == "DEGRADED"
    assert care_widget["metrics"]["patient_balance_total"] is None


def test_widget_update_route_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("WIDGET_API_KEY", "widget-secret")
    monkeypatch.setenv("WIDGET_API_KEY_HEADER", "X-API-Key")

    denied_response = client.post("/api/widgets/update", json=_sample_widget_update_payload())

    assert denied_response.status_code == 401

    allowed_response = client.post(
        "/api/widgets/update",
        json=_sample_widget_update_payload(),
        headers={"X-API-Key": "widget-secret"},
    )

    assert allowed_response.status_code == 202
    assert allowed_response.json()["auth_mode"] == "api-key"


def test_widget_update_rejects_without_api_key_in_production(monkeypatch):
    monkeypatch.delenv("WIDGET_API_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "production")

    response = client.post("/api/widgets/update", json=_sample_widget_update_payload())

    assert response.status_code == 403
    assert "WIDGET_API_KEY" in response.json()["detail"]


def test_widget_update_rejects_unset_app_env_without_api_key(monkeypatch):
    monkeypatch.delenv("WIDGET_API_KEY", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    response = client.post("/api/widgets/update", json=_sample_widget_update_payload())

    assert response.status_code == 403
    assert "WIDGET_API_KEY" in response.json()["detail"]


def test_widget_update_allows_local_fallback_in_development(monkeypatch):
    monkeypatch.delenv("WIDGET_API_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "development")

    response = client.post("/api/widgets/update", json=_sample_widget_update_payload())

    assert response.status_code == 202
    assert response.json()["auth_mode"] == "local"


def test_widget_update_payload_too_large(monkeypatch):
    monkeypatch.delenv("WIDGET_API_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    oversized_payload = _sample_widget_update_payload()
    oversized_payload["widgets"]["practice_financial_overview"]["metrics"]["padding"] = "x" * (512 * 1024)

    response = client.post("/api/widgets/update", json=oversized_payload)

    assert response.status_code == 413


def test_widget_update_rejects_malformed_payload(monkeypatch):
    monkeypatch.delenv("WIDGET_API_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "development")

    response = client.post("/api/widgets/update", json={"manager": "", "widgets": {}})

    assert response.status_code == 422


def test_widget_update_rejects_too_many_widgets(monkeypatch):
    monkeypatch.delenv("WIDGET_API_KEY", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    payload = _sample_widget_update_payload()
    payload["widgets"] = {
        f"widget_{index}": {"title": f"Widget {index}", "status": "SUCCESS", "metrics": {}}
        for index in range(21)
    }

    response = client.post("/api/widgets/update", json=payload)

    assert response.status_code == 422


def test_hal_admin_summary_route_returns_admin_payload():
    response = client.get("/api/hal9000/admin-summary", auth=basic_auth())

    assert response.status_code == 200
    payload = response.json()


def test_page_summary_flags_missing_quickbooks_detail_exports(monkeypatch):
    fresh_timestamp = datetime.now(timezone.utc).isoformat()

    monkeypatch.setattr(
        routes_module,
        "build_softdent_snapshot",
        lambda: {
            "available": True,
            "period": "2026-06",
            "provider_count": 1,
            "providers": [],
            "totals": {
                "production": 1500.0,
                "collections": 1100.0,
                "insurance": 600.0,
                "patient": 500.0,
            },
        },
    )
    monkeypatch.setattr(
        routes_module,
        "load_softdent_dashboard_rows",
        lambda: [{"period": "2026-06", "production": 1500.0, "collections": 1100.0}],
    )
    monkeypatch.setattr(routes_module, "load_softdent_ar_rows", lambda: [])
    monkeypatch.setattr(routes_module, "_build_softdent_latest_ar_snapshot_from_eod", lambda: None)
    monkeypatch.setattr(routes_module, "get_softdent_source_status", lambda: {"available": True, "modified_at_utc": fresh_timestamp})
    monkeypatch.setattr(routes_module, "get_softdent_claim_source_status", lambda: {"available": False})
    monkeypatch.setattr(routes_module, "get_softdent_coverage_metrics", lambda: {"trueOutstandingClaims": {}, "unsubmittedClaims": {}})

    def fake_fetch_quickbooks_sdk_summary(topic: str):
        if topic == "revenue":
            return [{"TotalIncome": 2000.0}]
        if topic == "expenses":
            return [{"TotalExpense": 1500.0}]
        return []

    monkeypatch.setattr(routes_module, "fetch_quickbooks_sdk_summary", fake_fetch_quickbooks_sdk_summary)
    monkeypatch.setattr(routes_module, "load_quickbooks_export_rows", lambda topic: [])
    monkeypatch.setattr(
        routes_module,
        "get_financial_source_status",
        lambda: {
            "softdent": {
                "available": True,
                "period": "2026-06",
                "provider_count": 1,
                "coverage": {"summary": "", "counts": {"missing": 0, "limited": 0, "available": 1}, "rows": []},
                "live_snapshot": {"available": True, "checked_at_utc": fresh_timestamp, "confidence_label": "verified", "review_required": False, "review_flags": [], "excerpt": "SoftDent live snapshot available."},
                "live_claims": {"available": False, "checked_at_utc": fresh_timestamp, "confidence_label": "manual review", "review_required": True, "review_flags": ["live claims missing"], "excerpt": "SoftDent claims export unavailable."},
            },
            "quickbooks": {
                "live_revenue": {"available": True, "modified_at_utc": fresh_timestamp, "checked_at_utc": fresh_timestamp, "confidence_label": "high confidence", "review_required": False, "review_flags": [], "excerpt": "QuickBooks approved revenue summary from sdk read-only query: TotalIncome=2000.0"},
                "live_expenses": {"available": True, "modified_at_utc": "", "checked_at_utc": fresh_timestamp, "confidence_label": "high confidence", "review_required": False, "review_flags": [], "excerpt": "QuickBooks approved expenses summary from sdk read-only query: TotalExpense=1500.0"},
                "live_ar": {"available": True, "modified_at_utc": "", "checked_at_utc": fresh_timestamp, "confidence_label": "high confidence", "review_required": False, "review_flags": [], "excerpt": "QuickBooks approved ar summary from sdk read-only query: no outstanding accounts receivable rows were returned."},
            },
        },
    )

    response = client.get("/api/hal9000/page-summary", auth=basic_auth())

    assert response.status_code == 200
    payload = response.json()
    assert payload["quickBooksExpenseCategories"] == []
    assert payload["sourceReview"]["quickBooks"]["status"] == "warning"
    assert payload["sourceReview"]["quickBooks"]["confidenceLabel"] == "review suggested"
    assert payload["sourceReview"]["quickBooks"]["reviewRequired"] is True
    assert "expense detail export missing" in payload["sourceReview"]["quickBooks"]["reviewFlags"]
    assert "Expense category detail export is unavailable" in payload["sourceReview"]["quickBooks"]["summary"]
    assert payload.get("latestAr") is None


def test_hal_field_timeframes_route_returns_tracked_registry(monkeypatch):
    monkeypatch.setattr(hal_orchestrator, "get_financial_source_status", _fake_hal_financial_sources)
    monkeypatch.setattr(hal_orchestrator, "_get_posting_queue_monitor_status", lambda: _fake_hal_monitor_status("posting-queue"))
    monkeypatch.setattr(hal_orchestrator, "_get_local_accounting_documents_monitor_status", lambda: _fake_hal_monitor_status("accounting-documents"))
    response = client.get("/api/hal9000/field-timeframes", auth=basic_auth())

    assert response.status_code == 200
    payload = response.json()
    registry = payload["registry"]
    assert payload["mode"] == "local-rag-phase-1"
    assert registry["tracked_field_count"] > 0
    assert registry["within_window_field_count"] == registry["tracked_field_count"]
    assert registry["compliance_percent"] >= 0
    dashboard_page = next(page for page in registry["pages"] if page["page_id"] == "dashboard")
    admin_page = next(page for page in registry["pages"] if page["page_id"] == "admin")
    posting_queue_page = next(page for page in registry["pages"] if page["page_id"] == "posting-queue")
    accounting_documents_page = next(page for page in registry["pages"] if page["page_id"] == "accounting-documents")
    assert dashboard_page["within_window_count"] == dashboard_page["field_count"]
    assert admin_page["within_window_count"] == admin_page["field_count"]
    assert posting_queue_page["within_window_count"] == posting_queue_page["field_count"]
    assert accounting_documents_page["within_window_count"] == accounting_documents_page["field_count"]


def test_reports_pull_status_returns_structured_sections():
    response = client.get("/api/reports/pull-status", auth=basic_auth())

    assert response.status_code == 200
    payload = response.json()
    assert "daily_refresh_enabled" in payload
    assert "last_refresh_date" in payload
    assert set(payload["status"].keys()) >= {"softdent", "quickbooks", "practice_central"}
    assert "summary" in payload["status"]["softdent"]


def test_hal_refresh_financial_sources_returns_structured_refresh_report():
    response = client.post("/api/hal9000/refresh-financial-sources", auth=basic_auth())

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "HAL refreshed SoftDent and QuickBooks financial sources."
    assert payload["actor"] == "admin"
    assert "refresh_report" in payload
    assert "financial_summary" in payload
    assert "admin_summary" in payload
    assert "hal_status" in payload
    refresh = payload["refresh_report"]["refresh"]
    assert {"softdent_pull", "quickbooks_pull", "practice_central_pull"} <= set(refresh.keys())
    assert "status" in refresh["softdent_pull"]


def test_softdent_import_route_writes_canonical_files_and_updates_pull_status(tmp_path):
    settings = app.state.settings
    original_import_dir = settings.softdent_import_dir
    original_source_dir = settings.softdent_source_dir
    original_auto_pull = settings.softdent_auto_pull_enabled

    settings.softdent_import_dir = tmp_path / "softdent"
    settings.softdent_source_dir = tmp_path / "source"
    settings.softdent_auto_pull_enabled = False

    try:
        response = client.post(
            "/softdent/import",
            auth=basic_auth(),
            files={
                "file": (
                    "softdent_upload.csv",
                    b"Month,Metric,Amount\n2026-06,Production,10\n2026-06,Collections,8\n",
                    "text/csv",
                )
            },
        )

        assert response.status_code == 200
        assert (settings.softdent_import_dir / "softdent_dashboard_data.csv").exists()
        assert (settings.softdent_import_dir / "softdent_dashboard_data.json").exists()

        pull_status = client.get("/api/reports/pull-status", auth=basic_auth()).json()
        softdent_status = pull_status["status"]["softdent"]
        assert softdent_status["status"] == "ready"
        assert "softdent_dashboard_data.csv" in softdent_status["files"]
    finally:
        settings.softdent_import_dir = original_import_dir
        settings.softdent_source_dir = original_source_dir
        settings.softdent_auto_pull_enabled = original_auto_pull


def test_softdent_import_route_accepts_approved_aggregate_report_files(tmp_path):
    settings = app.state.settings
    original_import_dir = settings.softdent_import_dir
    original_source_dir = settings.softdent_source_dir
    original_auto_pull = settings.softdent_auto_pull_enabled

    settings.softdent_import_dir = tmp_path / "softdent"
    settings.softdent_source_dir = tmp_path / "source"
    settings.softdent_auto_pull_enabled = False

    try:
        response = client.post(
            "/softdent/import",
            auth=basic_auth(),
            files={
                "file": (
                    "outstanding_claims_by_company.csv",
                    b"Payer,OutstandingAmount\nDelta Dental,1234.56\n",
                    "text/csv",
                )
            },
        )

        assert response.status_code == 200
        assert (settings.softdent_import_dir / "outstanding_claims_by_company.csv").exists()

        pull_status = client.get("/api/reports/pull-status", auth=basic_auth()).json()
        softdent_status = pull_status["status"]["softdent"]
        assert softdent_status["status"] == "ready"
        assert "outstanding_claims_by_company.csv" in softdent_status["files"]
    finally:
        settings.softdent_import_dir = original_import_dir
        settings.softdent_source_dir = original_source_dir
        settings.softdent_auto_pull_enabled = original_auto_pull


def test_hal_staged_import_accepts_quickbooks_csv(monkeypatch, tmp_path):
    monkeypatch.setattr(services_module, "get_ai_workspace_path", lambda: tmp_path)
    monkeypatch.setattr(services_module, "ensure_within_ai_workspace", lambda path: path)

    response = client.post(
        "/api/hal9000/staged-imports",
        auth=basic_auth(),
        json={
            "files": [
                {
                    "file_name": "quickbooks_profit_and_loss.csv",
                    "mime_type": "text/csv",
                    "content": "Date,Income,Expenses\n2026-06-01,100,25\n",
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["file_count"] == 1
    assert (tmp_path / "hal_staged_imports" / "quickbooks_profit_and_loss.csv").exists()


def test_hal_staged_import_rejects_softdent_files(monkeypatch, tmp_path):
    monkeypatch.setattr(services_module, "get_ai_workspace_path", lambda: tmp_path)
    monkeypatch.setattr(services_module, "ensure_within_ai_workspace", lambda path: path)

    response = client.post(
        "/api/hal9000/staged-imports",
        auth=basic_auth(),
        json={
            "files": [
                {
                    "file_name": "softdent_dashboard_data.json",
                    "mime_type": "application/json",
                    "content": "[]",
                }
            ]
        },
    )

    assert response.status_code == 400
    assert "not approved" in response.json()["detail"]


def test_hal_post_forwards_optional_summary_payload(monkeypatch):
    captured: dict[str, object] = {}

    def fake_answer_hal_question(*, question: str, actor: str, summary: dict[str, object] | None = None, session_id: str | None = None, roles=None, **kwargs):
        captured["question"] = question
        captured["actor"] = actor
        captured["summary"] = summary
        captured["session_id"] = session_id
        return {
            "mode": "local-rag-phase-1",
            "answer": "summary forwarded",
            "sanitized_question": question,
            "sanitization_findings": [],
            "retrieved_context": [],
            "guardrails": ["approved local read-only scope"],
            "audit_id": "hal-summary-forward-1",
            "access_policy": {
                "mode": "local-rag-phase-1",
                "auth_requirement": "auth",
                "network_boundary": "local",
                "audited": True,
                "allowed_sources": [],
                "disallowed_actions": [],
            },
            "review_actions": [],
            "voice_profile": {"lane": "primary", "label": "Primary response", "tone": "direct and grounded", "style_notes": []},
            "governance_notes": [],
        }

    monkeypatch.setattr(routes_module, "answer_hal_question", fake_answer_hal_question)

    with TestClient(app) as isolated_client:
        isolated_client.cookies.clear()
        response = isolated_client.post(
            "/hal9000",
            auth=basic_auth(),
            json={
                "question": "What is the latest daily gross production?",
                "session_id": "session-123",
                "summary": {
                    "latestDailyKpi": {
                        "gross_production": 7759,
                    }
                },
            },
        )

    assert response.status_code == 200
    assert captured["question"] == "What is the latest daily gross production?"
    assert captured["actor"] == "admin"
    assert captured["summary"] == {"latestDailyKpi": {"gross_production": 7759}}
    assert captured["session_id"] == "session-123"


def test_hal_second_opinion_post_forwards_optional_summary_payload(monkeypatch):
    captured: dict[str, object] = {}

    def fake_answer_hal_second_opinion_question(*, question: str, actor: str, summary: dict[str, object] | None = None, session_id: str | None = None, roles=None, **kwargs):
        captured["question"] = question
        captured["actor"] = actor
        captured["summary"] = summary
        captured["session_id"] = session_id
        return {
            "mode": "local-rag-phase-1:second-opinion",
            "answer": "second opinion forwarded",
            "sanitized_question": question,
            "sanitization_findings": [],
            "retrieved_context": [],
            "guardrails": ["approved local read-only scope"],
            "audit_id": "hal-second-opinion-forward-1",
            "access_policy": {
                "mode": "local-rag-phase-1",
                "auth_requirement": "auth",
                "network_boundary": "local",
                "audited": True,
                "allowed_sources": [],
                "disallowed_actions": [],
            },
            "review_actions": [],
            "voice_profile": {"lane": "second_opinion", "label": "Second opinion", "tone": "slower and more evaluative", "style_notes": []},
            "governance_notes": [],
        }

    monkeypatch.setattr(routes_module, "answer_hal_second_opinion_question", fake_answer_hal_second_opinion_question)

    with TestClient(app) as isolated_client:
        isolated_client.cookies.clear()
        response = isolated_client.post(
            "/hal9000/second-opinion",
            auth=basic_auth(),
            json={
                "question": "Give me a deeper second opinion on the latest daily gross production.",
                "session_id": "session-456",
                "summary": {
                    "latestDailyKpi": {
                        "gross_production": 7759,
                    }
                },
            },
        )

    assert response.status_code == 200
    assert captured["question"] == "Give me a deeper second opinion on the latest daily gross production."
    assert captured["actor"] == "admin"
    assert captured["summary"] == {"latestDailyKpi": {"gross_production": 7759}}
    assert isinstance(captured["session_id"], str)
    assert captured["session_id"].strip()


def test_hal_follow_up_isolated_by_session_id(monkeypatch):
    import app.hal.financial_tools as financial_tools

    def fake_claim_rows():
        return [
            {
                "PatientName": "John Doe",
                "MRN": "778899",
                "ClaimId": "CLM-1001",
                "ClaimStatus": "Denied",
                "Payer": "Delta Dental",
                "Procedure": "Crown buildup",
                "ServiceDate": "2026-06-01",
                "DenialReason": "Additional narrative requested by payer",
                "ClaimAmount": 915.4,
            },
            {
                "PatientName": "Jane Roe",
                "MRN": "112233",
                "ClaimId": "CLM-1002",
                "ClaimStatus": "Denied",
                "Payer": "MetLife",
                "Procedure": "Bridge repair",
                "ServiceDate": "2026-06-02",
                "DenialReason": "Need radiographs",
                "ClaimAmount": 642.1,
            },
        ]

    def fake_note_rows():
        return [
            {
                "PatientName": "John Doe",
                "MRN": "778899",
                "NoteDate": "2026-06-01",
                "Procedure": "Crown buildup",
                "ClinicalNote": "Patient has fractured cusp with recurrent decay and documented cold sensitivity.",
            },
            {
                "PatientName": "Jane Roe",
                "MRN": "112233",
                "NoteDate": "2026-06-02",
                "Procedure": "Bridge repair",
                "ClinicalNote": "Patient reports food impaction and recurrent discomfort near the abutment tooth.",
            },
        ]

    monkeypatch.setattr(financial_tools, "load_softdent_claim_rows", fake_claim_rows)
    monkeypatch.setattr(financial_tools, "load_softdent_clinical_note_rows", fake_note_rows)

    # The SoftDent read broker requires patient/clinical read roles before it
    # returns verified patient context. Grant the admin user those roles for
    # this test so we exercise the real patient-context retention + session
    # isolation path. monkeypatch restores the env automatically afterward.
    patient_read_users_json = json.dumps(
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
                    "softdent:patient:read",
                    "softdent:clinical:read",
                    "softdent:ledger:read",
                    "softdent:narrative:draft",
                ],
            }
        ]
    )
    monkeypatch.setenv("APP_AUTH_USERS_JSON", patient_read_users_json)
    clear_user_registry_cache()

    client.post(
        "/hal9000",
        auth=basic_auth(),
        json={"question": "Patient John Doe MRN 778899 needs an insurance narrative for the denied crown buildup claim.", "session_id": "session-a"},
    )
    client.post(
        "/hal9000",
        auth=basic_auth(),
        json={"question": "Patient Jane Roe MRN 112233 needs an insurance narrative for the denied bridge repair claim.", "session_id": "session-b"},
    )

    john_follow_up = client.post(
        "/hal9000",
        auth=basic_auth(),
        json={"question": "Based on the patient details I just gave you, draft the follow-up plan.", "session_id": "session-a"},
    )
    jane_follow_up = client.post(
        "/hal9000",
        auth=basic_auth(),
        json={"question": "Based on the patient details I just gave you, draft the follow-up plan.", "session_id": "session-b"},
    )

    assert john_follow_up.status_code == 200
    assert jane_follow_up.status_code == 200
    john_answer = john_follow_up.json()["answer"]
    jane_answer = jane_follow_up.json()["answer"]
    # Each session retains its own patient context and does not leak the other
    # session's patient.
    assert "Patient=John Doe" in john_answer
    assert "Jane Roe" not in john_answer
    assert "Patient=Jane Roe" in jane_answer
    assert "John Doe" not in jane_answer


def test_metrics_requires_admin_auth():
    response = client.get("/metrics")

    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


def test_metrics_allows_admin_auth():
    response = client.get("/metrics", auth=basic_auth())

    assert response.status_code == 200
    assert "http_requests_total" in response.text


def test_health_includes_tightened_csp_headers():
    response = client.get("/health", auth=basic_auth())

    assert response.status_code == 200
    csp = response.headers["Content-Security-Policy"]
    assert "base-uri 'self'" in csp
    assert "form-action 'self'" in csp
    assert "style-src-elem 'self'" in csp
    assert "style-src-attr 'unsafe-inline'" in csp


def test_import_routes_require_admin_role():
    response = client.post(
        "/softdent/import",
        auth=viewer_auth(),
        files={"file": ("softdent_dashboard_data.csv", "provider,period,production,collections\nDr A,2026-06,10,9\n", "text/csv")},
    )

    assert response.status_code == 403

    response = client.post(
        "/quickbooks/import",
        auth=viewer_auth(),
        files={"file": ("quickbooks_profit_loss.csv", "account,amount\nRevenue,100\n", "text/csv")},
    )

    assert response.status_code == 403


def test_softdent_import_rejects_unsupported_extension(tmp_path):
    settings = app.state.settings
    original_import_dir = settings.softdent_import_dir
    original_source_dir = settings.softdent_source_dir
    original_auto_pull = settings.softdent_auto_pull_enabled

    settings.softdent_import_dir = tmp_path / "softdent"
    settings.softdent_source_dir = tmp_path / "source"
    settings.softdent_auto_pull_enabled = False

    try:
        response = client.post(
            "/softdent/import",
            auth=basic_auth(),
            files={"file": ("softdent_upload.exe", b"not-a-real-export", "application/octet-stream")},
        )

        assert response.status_code == 400
        assert "Unsupported import file type" in response.json()["detail"]
    finally:
        settings.softdent_import_dir = original_import_dir
        settings.softdent_source_dir = original_source_dir
        settings.softdent_auto_pull_enabled = original_auto_pull


def test_softdent_import_rejects_unreadable_text_encoding(tmp_path):
    settings = app.state.settings
    original_import_dir = settings.softdent_import_dir
    original_source_dir = settings.softdent_source_dir
    original_auto_pull = settings.softdent_auto_pull_enabled

    settings.softdent_import_dir = tmp_path / "softdent"
    settings.softdent_source_dir = tmp_path / "source"
    settings.softdent_auto_pull_enabled = False

    try:
        response = client.post(
            "/softdent/import",
            auth=basic_auth(),
            files={
                "file": (
                    "softdent_upload.csv",
                    b"\xff\xfeM\x00o\x00n\x00t\x00h\x00,\x00M\x00e\x00t\x00r\x00i\x00c\x00\n\x00",
                    "text/csv",
                )
            },
        )

        assert response.status_code == 400
        assert "must use UTF-8 or Windows-1252 text encoding" in response.json()["detail"]
    finally:
        settings.softdent_import_dir = original_import_dir
        settings.softdent_source_dir = original_source_dir
        settings.softdent_auto_pull_enabled = original_auto_pull


def test_hal_post_redacts_internal_error_details(monkeypatch):
    def fake_answer_hal_question(*, question: str, actor: str, summary: dict[str, object] | None = None, session_id: str | None = None, roles=None, **kwargs):
        raise RuntimeError(r"C:\secrets\finance.db exploded")

    monkeypatch.setattr(routes_module, "answer_hal_question", fake_answer_hal_question)

    response = client.post(
        "/hal9000",
        auth=basic_auth(),
        json={"question": "What broke?"},
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail.startswith("Hal question failed. Reference ID: hal-")
    assert "finance.db" not in detail
    assert "RuntimeError" not in detail


def test_hal_second_opinion_post_redacts_internal_error_details(monkeypatch):
    def fake_answer_hal_second_opinion_question(*, question: str, actor: str, summary: dict[str, object] | None = None, session_id: str | None = None, roles=None, **kwargs):
        raise RuntimeError(r"C:\secrets\finance.db exploded")

    monkeypatch.setattr(routes_module, "answer_hal_second_opinion_question", fake_answer_hal_second_opinion_question)

    response = client.post(
        "/hal9000/second-opinion",
        auth=basic_auth(),
        json={"question": "What broke?"},
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail.startswith("Hal second opinion failed. Reference ID: hal-")
    assert "finance.db" not in detail
    assert "RuntimeError" not in detail


def test_hal_post_reuses_cookie_session_and_isolates_clients(monkeypatch):
    seen_session_ids: list[str] = []

    def fake_answer_hal_question(*, question: str, actor: str, summary: dict[str, object] | None = None, session_id: str | None = None, roles=None, **kwargs):
        assert session_id is not None
        seen_session_ids.append(session_id)
        return _fake_hal_ask_response(answer=f"session={session_id}")

    monkeypatch.setattr(routes_module, "answer_hal_question", fake_answer_hal_question)

    with TestClient(app) as first_client, TestClient(app) as second_client:
        first_response = first_client.post("/hal9000", auth=basic_auth(), json={"question": "What changed?"})
        second_response = first_client.post("/hal9000", auth=basic_auth(), json={"question": "And now?"})
        third_response = second_client.post("/hal9000", auth=basic_auth(), json={"question": "Separate browser?"})

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert third_response.status_code == 200
    assert len(seen_session_ids) == 3
    assert seen_session_ids[0] == seen_session_ids[1]
    assert seen_session_ids[0] != seen_session_ids[2]
    assert routes_module.HAL_SESSION_COOKIE_NAME in first_response.headers["set-cookie"]


def test_hal_post_ignores_payload_session_id_when_cookie_session_exists(monkeypatch):
    seen_session_ids: list[str] = []

    def fake_answer_hal_question(*, question: str, actor: str, summary: dict[str, object] | None = None, session_id: str | None = None, roles=None, **kwargs):
        assert session_id is not None
        seen_session_ids.append(session_id)
        return _fake_hal_ask_response(answer=f"session={session_id}")

    monkeypatch.setattr(routes_module, "answer_hal_question", fake_answer_hal_question)

    with TestClient(app) as client:
        first_response = client.post("/hal9000", auth=basic_auth(), json={"question": "Start a thread."})
        second_response = client.post(
            "/hal9000",
            auth=basic_auth(),
            json={"question": "Try to override it.", "session_id": "payload-session-override"},
        )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert len(seen_session_ids) == 2
    assert seen_session_ids[0] == seen_session_ids[1]
    assert seen_session_ids[1] != "payload-session-override"


def test_resolve_hal_session_id_prefers_cookie_then_payload():
    cookie_request = type("DummyRequest", (), {"cookies": {routes_module.HAL_SESSION_COOKIE_NAME: "cookie-session"}})()
    payload_only_request = type("DummyRequest", (), {"cookies": {}})()

    assert routes_module._resolve_hal_session_id(cookie_request, "payload-session") == "cookie-session"
    assert routes_module._resolve_hal_session_id(payload_only_request, "payload-session") == "payload-session"


def test_hal_post_sets_secure_cookie_on_https_requests(monkeypatch):
    monkeypatch.setattr(routes_module, "answer_hal_question", lambda **kwargs: _fake_hal_ask_response(answer="secure-cookie"))

    with TestClient(app, base_url="https://testserver") as https_client:
        response = https_client.post("/hal9000", auth=basic_auth(), json={"question": "What changed?"})

    assert response.status_code == 200
    assert "secure" in response.headers["set-cookie"].lower()


def test_hal_post_sets_secure_cookie_when_forwarded_proto_is_https(monkeypatch):
    monkeypatch.setattr(routes_module, "answer_hal_question", lambda **kwargs: _fake_hal_ask_response(answer="forwarded-secure-cookie"))

    with TestClient(app) as proxy_client:
        response = proxy_client.post(
            "/hal9000",
            auth=basic_auth(),
            json={"question": "What changed behind the proxy?"},
            headers={"x-forwarded-proto": "https"},
        )

    assert response.status_code == 200
    assert "secure" in response.headers["set-cookie"].lower()

def test_unauthorized():
    response = client.get("/api/hal9000/admin-summary")
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


def test_password_hash_configuration_authenticates(monkeypatch):
    hashed_users_json = json.dumps(
        [
            {
                "username": "admin",
                "display_name": "Administrator",
                "password_hash": hash_password("password"),
                "roles": ["dashboard:read", "hal:operator", "hal:index:refresh", "admin"],
            },
            {
                "username": "viewer",
                "display_name": "Viewer",
                "password_hash": hash_password("viewer-password"),
                "roles": ["dashboard:read"],
            },
        ]
    )
    monkeypatch.setenv("APP_AUTH_USERS_JSON", hashed_users_json)
    clear_user_registry_cache()

    response = client.get("/health", auth=basic_auth())

    assert response.status_code == 200
    assert validate_auth_configuration()["user_count"] == 2


def test_service_test_client_supports_password_hash_configuration(monkeypatch):
    hashed_users_json = json.dumps(
        [
            {
                "username": "admin",
                "display_name": "Administrator",
                "password_hash": hash_password("password"),
                "roles": ["dashboard:read", "hal:operator", "hal:index:refresh", "admin"],
            }
        ]
    )
    monkeypatch.setenv("APP_AUTH_USERS_JSON", hashed_users_json)
    clear_user_registry_cache()

    with services_module._service_test_client(app, required_role="admin") as internal_client:
        response = internal_client.get("/api/admin")

    assert response.status_code == 501
    assert response.json() == {"detail": "Admin API is not implemented in this service."}


@pytest.mark.parametrize(
    ("path", "detail"),
    [
        ("/softdent", "SoftDent page is not implemented in this service."),
        ("/quickbooks", "QuickBooks page is not implemented in this service."),
        ("/accounts-receivable", "Accounts Receivable page is not implemented in this service."),
        ("/reconciliation", "Reconciliation page is not implemented in this service."),
        ("/trends", "Trends page is not implemented in this service."),
        ("/ebitda", "EBITDA page is not implemented in this service."),
        ("/claims", "Claims page is not implemented in this service."),
        ("/admin", "Admin page is not implemented in this service."),
        ("/reports", "Reports page is not implemented in this service."),
        ("/api/admin", "Admin API is not implemented in this service."),
        ("/api/reconciliation", "Reconciliation API is not implemented in this service."),
        ("/api/reports/practice-central-delta", "Practice Central delta report is not implemented in this service."),
    ],
)
def test_placeholder_routes_return_not_implemented(path, detail):
    response = client.get(path, auth=basic_auth())

    assert response.status_code == 501
    assert response.json() == {"detail": detail}


def test_validate_auth_configuration_requires_json(monkeypatch):
    os.environ.pop("APP_AUTH_USERS_JSON", None)
    clear_user_registry_cache()

    monkeypatch.setattr("app.auth.get_env_setting", lambda name, default="": "" if name == "APP_AUTH_USERS_JSON" else default)

    with pytest.raises(RuntimeError, match="APP_AUTH_USERS_JSON is required"):
        validate_auth_configuration()


def test_validate_auth_configuration_rejects_malformed_json():
    os.environ["APP_AUTH_USERS_JSON"] = "{bad json"
    clear_user_registry_cache()

    with pytest.raises(RuntimeError, match="not valid JSON"):
        validate_auth_configuration()


def test_validate_auth_configuration_requires_session_secret_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("APP_AUTH_SESSION_SECRET", raising=False)
    clear_user_registry_cache()

    with pytest.raises(RuntimeError, match="APP_AUTH_SESSION_SECRET is required"):
        validate_auth_configuration()


def test_validate_auth_configuration_requires_session_secret_when_app_env_unset(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_AUTH_SESSION_SECRET", raising=False)
    clear_user_registry_cache()

    with pytest.raises(RuntimeError, match="APP_AUTH_SESSION_SECRET is required"):
        validate_auth_configuration()


def test_validate_auth_configuration_allows_session_secret_fallback_in_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("APP_AUTH_SESSION_SECRET", raising=False)
    clear_user_registry_cache()

    assert validate_auth_configuration()["user_count"] == 3


def test_claims_summary_unavailable_metric_is_null_not_zero():
    from app.routes import _build_softdent_claims_summary

    result = _build_softdent_claims_summary(
        {
            "trueOutstandingClaims": {"available": False, "totalAmount": None, "itemCount": 0},
            "unsubmittedClaims": {"available": False, "totalAmount": None, "itemCount": 0},
        }
    )
    assert result["available"] is False
    assert result["true_outstanding_claims_amount"] is None
    assert result["true_outstanding_claims_count"] is None
    assert result["unsubmitted_claims_amount"] is None
    assert result["unsubmitted_claims_count"] is None


def test_claims_summary_verified_zero_is_preserved():
    from app.routes import _build_softdent_claims_summary

    result = _build_softdent_claims_summary(
        {
            "trueOutstandingClaims": {"available": True, "totalAmount": 0, "itemCount": 0},
            "unsubmittedClaims": {"available": True, "totalAmount": 0, "itemCount": 0},
        }
    )
    assert result["available"] is True
    assert result["true_outstanding_claims_amount"] == 0.0
    assert result["unsubmitted_claims_amount"] == 0.0


def test_claims_summary_mixed_availability_nulls_only_unavailable_metric():
    from app.routes import _build_softdent_claims_summary

    result = _build_softdent_claims_summary(
        {
            "trueOutstandingClaims": {"available": True, "totalAmount": 1200.5, "itemCount": 3},
            "unsubmittedClaims": {"available": False, "totalAmount": None, "itemCount": 0},
        }
    )
    assert result["available"] is True
    assert result["true_outstanding_claims_amount"] == 1200.5
    assert result["true_outstanding_claims_count"] == 3
    assert result["unsubmitted_claims_amount"] is None
    assert result["unsubmitted_claims_count"] is None
