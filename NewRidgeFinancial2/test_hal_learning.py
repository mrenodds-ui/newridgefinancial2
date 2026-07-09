"""Tests for HAL learn-as-you-go module."""

from __future__ import annotations

from hal_learning import (
    extract_remember_candidate,
    format_session_context_block,
    learning_status,
    remember_import_sync_observation,
    update_session_context,
)


def test_extract_remember_candidate():
    assert extract_remember_candidate("remember this: Delta requires narratives within 30 days")
    assert "Delta" in extract_remember_candidate("remember this: Delta requires narratives within 30 days")


def test_session_context_roundtrip(tmp_path, monkeypatch):
    from hal_learning import SESSION_CONTEXT_PATH

    path = tmp_path / "hal_session_context.json"
    monkeypatch.setattr("hal_learning.SESSION_CONTEXT_PATH", path)
    update_session_context(claim_id="CLM-1", payer="Delta Dental", topic="narrative appeal")
    block = format_session_context_block()
    assert "CLM-1" in block
    assert "Delta Dental" in block


def test_remember_import_sync_observation(tmp_path, monkeypatch):
    from hal_learning import LEARNED_MEMORIES_PATH

    learned = tmp_path / "learned.jsonl"
    monkeypatch.setattr("hal_learning.LEARNED_MEMORIES_PATH", learned)
    monkeypatch.setattr("knowledge_memory_store.LEARNED_MEMORIES_PATH", learned)

    sync = {
        "syncedAt": "2026-07-08T12:00:00Z",
        "softdent": {"copied": ["softdent_claims_export.csv"]},
        "quickbooks": {"copied": []},
        "diagnostics": {"summary": {"connected": 5, "stale": 1, "missing": 2}},
        "warnings": [],
    }
    first = remember_import_sync_observation(sync)
    assert first and first.get("ok")
    second = remember_import_sync_observation(sync)
    assert second is None


def test_learning_status():
    status = learning_status()
    assert status["ok"]
    assert status["governedCount"] >= 10_000
