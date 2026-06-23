import json
import os

from fastapi.testclient import TestClient

from app.auth import clear_user_registry_cache
from app.main import app


TEST_AUTH_USERS_JSON = json.dumps(
    [
        {
            "username": "hal_operator",
            "display_name": "HAL Operator",
            "password": "hal-password",
            "roles": ["dashboard:read", "hal:operator", "hal:index:refresh"],
        }
    ]
)

os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON

client = TestClient(app)


def setup_function():
    os.environ["APP_AUTH_USERS_JSON"] = TEST_AUTH_USERS_JSON
    clear_user_registry_cache()


def operator_auth():
    return ("hal_operator", "hal-password")


def test_accounting_policy_answer_returns_citations():
    refresh = client.post("/api/hal9000/refresh-index", auth=operator_auth())
    assert refresh.status_code == 200

    response = client.post(
        "/api/hal9000/accounting/policy-answer",
        auth=operator_auth(),
        json={
            "question": "How should prepaid insurance be treated at period end?",
            "topic": "prepaids",
            "accounting_standard": "GAAP",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "local-rag-phase-1"
    assert payload["review_required"] is True
    assert payload["confidence"] in {"medium", "low"}
    assert payload["audit_id"].startswith("hal-")
    assert payload["citations"]
    assert payload["accounting_standard"] == "GAAP"