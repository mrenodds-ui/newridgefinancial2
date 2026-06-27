from __future__ import annotations

from pathlib import Path

import pytest

from app.hal.memory_workflow import (
    APPROVED_STATUS,
    MemoryWorkflowError,
    approve_hal_memory,
    list_governed_hal_memories,
    propose_hal_memory,
    revoke_hal_memory,
    validate_memory_proposal_text,
)
from app.hal.storage import get_hal_memory, list_hal_memory_events


@pytest.fixture()
def isolated_hal_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HAL_ALLOWED_BASE_PATH", str(tmp_path))
    db_path = tmp_path / "hal_memory_test.sqlite3"
    monkeypatch.setenv("HAL_SQLITE_PATH", str(db_path))
    return db_path


def test_memory_workflow_propose_approve_and_revoke(isolated_hal_storage: Path) -> None:
    proposed = propose_hal_memory(
        actor="admin",
        text="Daily huddle notes should stay local and require staff review before operational use.",
        category="operator_playbooks",
        source="unit test",
    )

    memory_id = proposed["memory_id"]
    assert memory_id.startswith("office-")
    assert proposed["status"] == "proposed"
    assert proposed["sensitivity_level"] == "internal_safe"
    assert proposed["must_not_override"] == ["guardrails", "auth", "runtime_status", "hal_ask_request"]
    assert get_hal_memory(memory_id) is not None

    approved = approve_hal_memory(memory_id=memory_id, actor="admin", note="Approved for test.")
    assert approved["status"] == APPROVED_STATUS
    assert approved["approved_by"] == "admin"

    listed = list_governed_hal_memories(status=APPROVED_STATUS)
    assert [item["memory_id"] for item in listed] == [memory_id]

    revoked = revoke_hal_memory(memory_id=memory_id, actor="admin", note="No longer needed.")
    assert revoked["status"] == "revoked"

    events = list_hal_memory_events(memory_id=memory_id)
    assert [event["event_type"] for event in events] == ["proposed", "approved", "revoked"]
    assert events[-1]["snapshot"]["status"] == "revoked"


def test_memory_workflow_rejects_phi_and_unsafe_external_actions(isolated_hal_storage: Path) -> None:
    with pytest.raises(MemoryWorkflowError):
        validate_memory_proposal_text("Patient Jane Roe should be called after treatment.")

    with pytest.raises(MemoryWorkflowError):
        validate_memory_proposal_text("Gateway submit is allowed for operators.")


def test_memory_workflow_rejects_unsupported_category(isolated_hal_storage: Path) -> None:
    with pytest.raises(MemoryWorkflowError, match="Unsupported memory category"):
        propose_hal_memory(
            actor="admin",
            text="Keep local drafts review-only before operational use.",
            category="patient_specific_fact",
        )
