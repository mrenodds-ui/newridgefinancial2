"""Unit tests for HAL knowledge/memory retrieval filters.

No live ``/api/hal9000`` calls and no Ollama dependency.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.hal.knowledge_memory import (
    build_knowledge_memory_documents,
    filter_indexable_memories,
    is_memory_indexable,
    is_memory_stale,
    load_memory_registry,
    memory_contains_forbidden_content,
    memory_to_index_document,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEMORIES_PATH = PROJECT_ROOT / "docs" / "hal_knowledge" / "memories.jsonl"


@pytest.fixture(scope="module")
def registry() -> list[dict]:
    return load_memory_registry(MEMORIES_PATH)


def test_load_registry_from_seed_file(registry: list[dict]):
    assert len(registry) >= 15


def test_proposed_memory_excluded(registry: list[dict]):
    proposed = next(m for m in registry if m["id"] == "proposed-gateway-submit-allowed")
    assert proposed["status"] == "proposed"
    assert is_memory_indexable(proposed) is False


def test_approved_safety_memory_included(registry: list[dict]):
    memory = next(m for m in registry if m["id"] == "no-external-submit-actions")
    assert is_memory_indexable(memory) is True


def test_build_documents_only_from_indexable(registry: list[dict]):
    documents = build_knowledge_memory_documents(MEMORIES_PATH)
    ids = {doc["source_id"] for doc in documents}
    assert "memory-no-external-submit-actions" in ids
    assert "memory-proposed-gateway-submit-allowed" not in ids
    assert all(doc["category"] == "knowledge_memory" for doc in documents)
    assert all("guidance only" in doc["sanitized_content"].lower() for doc in documents)


def test_memory_to_index_document_prefixes_guidance(registry: list[dict]):
    memory = next(m for m in registry if m["id"] == "hal-frontend-lane-port")
    doc = memory_to_index_document(memory)
    assert doc["source_id"] == "memory-hal-frontend-lane-port"
    assert "11434" in doc["sanitized_content"]
    assert "guidance only" in doc["sanitized_content"].lower()


def test_forbidden_content_detector():
    assert memory_contains_forbidden_content("Gateway submit is allowed for operators.")
    assert memory_contains_forbidden_content("PatientName,MRN,ClaimId")
    assert not memory_contains_forbidden_content("HAL frontend lane uses port 11434.")


def test_stale_memory_excluded_by_default(registry: list[dict]):
    stale_candidate = {
        "id": "stale-test",
        "category": "deployment_notes",
        "text": "Old deployment note for contract test only.",
        "source": "test",
        "created_at": "2025-01-01T00:00:00Z",
        "last_verified_at": "2025-01-01T00:00:00Z",
        "confidence": "high",
        "scope": "deployment",
        "staleness_rule": "expires_30d",
        "sensitivity_level": "internal_safe",
        "status": "approved",
        "must_not_override": ["runtime_status"],
    }
    assert is_memory_stale(stale_candidate)
    assert is_memory_indexable(stale_candidate) is False
    assert is_memory_indexable(stale_candidate, include_stale=True) is True


def test_runtime_check_required_not_marked_stale(registry: list[dict]):
    memory = next(m for m in registry if m["id"] == "hal-backend-lane-port")
    assert memory["staleness_rule"] == "runtime_check_required"
    assert is_memory_stale(memory) is False


def test_low_confidence_excluded():
    memory = {
        "id": "low-confidence-test",
        "category": "future_tasks",
        "text": "Low confidence backlog item for filter test.",
        "source": "test",
        "created_at": "2026-06-26T00:00:00Z",
        "last_verified_at": "2026-06-26T00:00:00Z",
        "confidence": "low",
        "scope": "testing",
        "staleness_rule": "expires_30d",
        "sensitivity_level": "internal_safe",
        "status": "approved",
        "must_not_override": ["guardrails"],
    }
    assert is_memory_indexable(memory) is False


def test_filter_indexable_count_less_than_registry(registry: list[dict]):
    indexable = filter_indexable_memories(registry)
    assert len(indexable) < len(registry)
    assert len(indexable) >= 10
