"""REC-009 Voice Context Carry — session handoff + seed/trigger logic."""

from __future__ import annotations

import json
import time

import pytest

import hal_learning
from hal_learning import format_session_context_block, load_session_context, update_session_context


@pytest.fixture
def isolated_session_context(tmp_path, monkeypatch):
    path = tmp_path / "rec009_session.json"
    monkeypatch.setattr(hal_learning, "SESSION_CONTEXT_PATH", path)
    return path


class TestSessionContextPersistence:
    def test_claim_id_persisted(self, isolated_session_context):
        result = update_session_context(
            claim_id="CLM-REC009-001",
            page="claims",
            topic="narrative_generation",
            payer="TestPayer",
        )
        assert result["ok"] is True
        assert result["context"]["lastClaimId"] == "CLM-REC009-001"
        ctx = load_session_context()
        assert ctx["lastClaimId"] == "CLM-REC009-001"
        assert ctx["lastPage"] == "claims"

    def test_context_survives_partial_update(self, isolated_session_context):
        update_session_context(claim_id="CLM-001", page="claims")
        update_session_context(page="narratives", topic="voice_carry")
        ctx = load_session_context()
        assert ctx["lastClaimId"] == "CLM-001"
        assert ctx["lastPage"] == "narratives"

    def test_format_includes_claim(self, isolated_session_context):
        update_session_context(claim_id="CLM-789", payer="Delta Dental")
        block = format_session_context_block()
        assert "Last claim: CLM-789" in block
        assert "Last payer: Delta Dental" in block


class TestNarrativeSeedLogic:
    def test_seed_consumption_valid(self):
        seed = {
            "claimId": "CLM-999",
            "voiceCarry": True,
            "timestamp": time.time() * 1000,
        }
        ttl_ms = 300000
        assert seed["voiceCarry"]
        assert (time.time() * 1000 - seed["timestamp"]) < ttl_ms

    def test_seed_expiry(self):
        old_seed = {"claimId": "CLM-OLD", "voiceCarry": True, "timestamp": 0}
        assert (time.time() * 1000 - old_seed["timestamp"]) > 300000

    def test_seed_no_voice_flag(self):
        seed = {"claimId": "CLM-001", "voiceCarry": False}
        assert not seed.get("voiceCarry")

    def test_voice_carry_json_roundtrip(self, tmp_path):
        path = tmp_path / "voice-carry.json"
        payload = {
            "claimId": "CLM-123",
            "voiceCarry": True,
            "timestamp": int(time.time() * 1000),
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["claimId"] == "CLM-123"
        assert loaded["voiceCarry"] is True


class TestVoiceTriggerDetection:
    TRIGGERS = [
        "this claim",
        "the claim i just clicked",
        "that claim",
        "for this",
        "appeal for this",
        "draft appeal",
        "letter for this",
    ]

    def test_detects_contextual_reference(self):
        said = "draft appeal for this claim"
        assert any(t in said.lower() for t in self.TRIGGERS)

    def test_no_false_positive(self):
        said = "schedule follow up next week"
        assert not any(t in said.lower() for t in self.TRIGGERS)

    def test_claim_ref_injection(self):
        said = "write appeal for this claim"
        claim_id = "CLM-123"
        if any(t in said.lower() for t in self.TRIGGERS):
            final = f"[ClaimRef:{claim_id}] {said}"
        else:
            final = said
        assert final.startswith("[ClaimRef:CLM-123]")
