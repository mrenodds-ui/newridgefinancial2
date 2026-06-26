"""Contract/schema-only validation for the HAL knowledge/memory registry.

Validates ``docs/hal_knowledge/memories.jsonl`` and related schema assets.
No live ``/api/hal9000`` calls and no Ollama dependency.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = PROJECT_ROOT / "docs" / "hal_knowledge"
SCHEMA_PATH = KNOWLEDGE_DIR / "schema.json"
CATEGORIES_PATH = KNOWLEDGE_DIR / "categories.json"
MEMORIES_PATH = KNOWLEDGE_DIR / "memories.jsonl"
README_PATH = KNOWLEDGE_DIR / "README.md"
RUNTIME_WORKFLOW_PATH = KNOWLEDGE_DIR / "runtime_workflow.md"

ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

CATEGORIES = {
    "project_architecture",
    "hal_runtime_lanes",
    "known_workflows",
    "safety_policy",
    "insurance_narratives",
    "softdent_exports",
    "quickbooks_readonly",
    "known_bugs_and_fixes",
    "operator_playbooks",
    "deployment_notes",
    "test_results",
    "future_tasks",
}

CONFIDENCE_LEVELS = {"high", "medium", "low"}
SCOPES = {
    "global",
    "hal",
    "insurance_narratives",
    "softdent",
    "quickbooks",
    "local_ai",
    "testing",
    "deployment",
}
STALENESS_RULES = {
    "never",
    "verify_monthly",
    "runtime_check_required",
    "expires_30d",
    "expires_90d",
}
SENSITIVITY_LEVELS = {"public_docs", "internal_safe", "restricted", "prohibited"}
STATUSES = {"proposed", "approved", "deprecated", "revoked"}
MUST_NOT_OVERRIDE = {
    "runtime_status",
    "auth",
    "guardrails",
    "source_availability",
    "external_submission_policy",
    "hal_ask_request",
}

REQUIRED_FIELDS = {
    "id",
    "category",
    "text",
    "source",
    "created_at",
    "last_verified_at",
    "confidence",
    "scope",
    "staleness_rule",
    "sensitivity_level",
    "status",
    "must_not_override",
}

FORBIDDEN_MEMORY_PHRASES = (
    "patientname,mrn,claimid",
    "api_key",
    "password=",
    "secret=",
    "gateway submit is allowed",
)


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_memories() -> list[dict]:
    memories: list[dict] = []
    for line_number, raw_line in enumerate(MEMORIES_PATH.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"Invalid JSON on line {line_number}: {exc}") from exc
        memories.append(entry)
    return memories


@pytest.fixture(scope="module")
def memories() -> list[dict]:
    return _load_memories()


@pytest.fixture(scope="module")
def categories_doc() -> dict:
    return _load_json(CATEGORIES_PATH)


def test_knowledge_files_exist():
    for path in (
        SCHEMA_PATH,
        CATEGORIES_PATH,
        MEMORIES_PATH,
        README_PATH,
        RUNTIME_WORKFLOW_PATH,
    ):
        assert path.is_file(), f"Missing knowledge file: {path}"


def test_categories_cover_schema_enums(categories_doc: dict):
    defined = set(categories_doc.get("categories", {}).keys())
    assert CATEGORIES <= defined


def test_memory_count_reasonable(memories: list[dict]):
    assert len(memories) >= 15, f"Expected seed memories, found {len(memories)}"


def test_memory_ids_unique_and_well_formed(memories: list[dict]):
    seen: set[str] = set()
    for memory in memories:
        memory_id = memory["id"]
        assert ID_PATTERN.match(memory_id), f"Bad id: {memory_id!r}"
        assert memory_id not in seen, f"Duplicate id: {memory_id}"
        seen.add(memory_id)


def test_required_fields_and_enums(memories: list[dict]):
    for memory in memories:
        missing = REQUIRED_FIELDS - set(memory.keys())
        assert not missing, f"{memory.get('id')}: missing {missing}"
        assert memory["category"] in CATEGORIES, memory["id"]
        assert memory["confidence"] in CONFIDENCE_LEVELS, memory["id"]
        assert memory["scope"] in SCOPES, memory["id"]
        assert memory["staleness_rule"] in STALENESS_RULES, memory["id"]
        assert memory["sensitivity_level"] in SENSITIVITY_LEVELS, memory["id"]
        assert memory["status"] in STATUSES, memory["id"]
        assert isinstance(memory["must_not_override"], list) and memory["must_not_override"], memory["id"]
        for token in memory["must_not_override"]:
            assert token in MUST_NOT_OVERRIDE, f"{memory['id']}: bad must_not_override {token!r}"


def test_approved_memories_include_core_safety_rules(memories: list[dict]):
    approved_ids = {m["id"] for m in memories if m["status"] == "approved"}
    required = {
        "missing-softdent-ar-unavailable",
        "no-external-submit-actions",
        "no-raw-csv-exposure",
        "no-ar-inference-from-totals",
        "knowledge-memory-governed-layer",
        "hal-internal-staff-assistant-stance",
    }
    missing = required - approved_ids
    assert not missing, f"Missing approved core memories: {missing}"


def test_proposed_and_prohibited_not_indexable_by_policy(memories: list[dict]):
    from app.hal.knowledge_memory import is_memory_indexable

    for memory in memories:
        if memory["status"] != "approved":
            assert is_memory_indexable(memory) is False, memory["id"]
        if memory["sensitivity_level"] in {"restricted", "prohibited"}:
            assert is_memory_indexable(memory) is False, memory["id"]


def test_no_approved_memory_authorizes_external_actions(memories: list[dict]):
    bad_phrases = (
        "gateway submit is allowed",
        "may submit to gateway",
        "will fax",
        "will upload",
    )
    for memory in memories:
        if memory["status"] != "approved":
            continue
        lowered = memory["text"].lower()
        for phrase in bad_phrases:
            assert phrase not in lowered, f"{memory['id']}: authorizes external action"


def test_no_obvious_phi_secrets_or_raw_rows_in_approved_memories(memories: list[dict]):
    approved_blob = json.dumps([m for m in memories if m["status"] == "approved"]).lower()
    for forbidden in FORBIDDEN_MEMORY_PHRASES:
        assert forbidden not in approved_blob, f"Approved memories must not contain {forbidden!r}"


def test_missing_ar_memories_forbid_zero_and_inference(memories: list[dict]):
    ar_memories = [m for m in memories if m["id"] == "missing-softdent-ar-unavailable"]
    assert ar_memories, "missing-softdent-ar-unavailable memory required"
    memory = ar_memories[0]
    assert memory["status"] == "approved"
    text = memory["text"].lower()
    assert "unavailable" in text
    assert "$0" in text or "not as $0" in text or "not $0" in text


def test_future_tasks_low_confidence_or_backlog_category(memories: list[dict]):
    future = [m for m in memories if m["category"] == "future_tasks" and m["status"] == "approved"]
    for memory in future:
        assert memory["confidence"] in {"low", "medium"}, memory["id"]
        assert "must_not_override" in memory and "guardrails" in memory["must_not_override"]


def test_staleness_expires_at_parsable(memories: list[dict]):
    for memory in memories:
        for field in ("created_at", "last_verified_at"):
            value = memory[field]
            assert isinstance(value, str) and value.strip(), f"{memory['id']}: {field}"
        expires_at = memory.get("expires_at")
        if expires_at:
            normalized = str(expires_at).replace("Z", "+00:00")
            datetime.fromisoformat(normalized)


def test_registry_includes_at_least_one_proposed_fixture(memories: list[dict]):
    proposed = [m for m in memories if m["status"] == "proposed"]
    assert proposed, "Need at least one proposed memory for governance tests"
    assert any(m["sensitivity_level"] == "prohibited" for m in proposed)


def test_readme_states_not_allowlist_or_bypass():
    readme = README_PATH.read_text(encoding="utf-8").lower()
    assert "not" in readme and "allowlist" in readme
    assert "bypass" in readme
    assert "evals/hal_intent_library" in readme or "intent" in readme
