from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest

from app import ai_local_config as config
import app.hal.orchestrator as hal_orchestrator
from app.ai_local_config import LocalAIConfigError
from app.hal.audit import get_hal_audit
from app.tests.lane_routing_test_helpers import (
    BACKEND_LANE_MODEL,
    BACKEND_LANE_URL,
    FRONTEND_LANE_URL,
    make_require_lane_runtime_mock,
)


@pytest.fixture(autouse=True)
def _clear_ai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AI_FRONTEND_BASE_URL",
        "AI_BACKEND_BASE_URL",
        "AI_FRONTEND_MODEL",
        "AI_BACKEND_MODEL",
        "OLLAMA_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def _hal_runtime_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_dir = os.path.join(os.path.dirname(__file__), ".second_opinion_runtime", uuid4().hex)
    os.environ["HAL_ALLOWED_BASE_PATH"] = runtime_dir
    os.environ["HAL_SQLITE_PATH"] = os.path.join(runtime_dir, "hal_test.sqlite3")
    os.environ["HAL_CHROMA_PATH"] = os.path.join(runtime_dir, "hal_chroma")


def test_resolve_lane_profile_chat_second_opinion_uses_backend_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_BACKEND_BASE_URL", "http://backend:11435")
    monkeypatch.setenv("AI_BACKEND_MODEL", "backend-30b")

    payload = config.load_local_model_profile_config()
    profile = config.resolve_lane_profile(payload, "chat_second_opinion")

    assert config.profile_lane("chat_second_opinion") == "backend"
    assert config.resolve_profile_base_url("chat_second_opinion") == "http://backend:11435"
    assert config.get_model_for_profile_alias("chat_second_opinion") == "backend-30b"
    assert profile["model"] == "backend-30b"


def test_second_opinion_calls_backend_lane_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_BACKEND_BASE_URL", BACKEND_LANE_URL)
    monkeypatch.setenv("AI_BACKEND_MODEL", BACKEND_LANE_MODEL)

    captured: dict[str, object] = {}

    def fake_generate_response_result(*, base_url, profile, prompt, timeout_seconds, seed=None):
        assert base_url == BACKEND_LANE_URL
        assert ":11434" not in base_url
        assert ":11436" not in base_url
        assert profile["model"] == BACKEND_LANE_MODEL
        captured["base_url"] = base_url
        captured["profile"] = profile
        captured["prompt"] = prompt
        return {"response_text": "Backend second opinion on collections risk."}

    monkeypatch.setattr(
        hal_orchestrator,
        "require_lane_runtime",
        make_require_lane_runtime_mock(expected_alias="chat_second_opinion"),
    )
    monkeypatch.setattr(hal_orchestrator, "generate_response_result", fake_generate_response_result)
    monkeypatch.setattr(hal_orchestrator, "retrieve_relevant_context", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "get_live_financial_context", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_hardware_snippets", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_softdent_aggregate_snippets", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_live_report_snippets", lambda question: [])
    monkeypatch.setattr(
        hal_orchestrator,
        "get_controlled_patient_context",
        lambda question: {"matched": False, "snippets": [], "narrative": ""},
    )

    payload = hal_orchestrator.answer_hal_second_opinion_question(
        question="Give me a deeper second opinion on collections risk.",
        actor="hal_operator",
        summary={"latestDailyKpi": {"gross_production": 7759}},
    )

    assert payload["mode"] == "local-rag-phase-1:second-opinion"
    assert payload["answer"] == "Backend second opinion on collections risk."
    assert payload["local_ai_unavailable"] is None
    assert captured["base_url"] == BACKEND_LANE_URL
    assert captured["profile"]["model"] == BACKEND_LANE_MODEL
    assert captured["profile"]["num_predict"] == hal_orchestrator.SECOND_OPINION_NUM_PREDICT
    assert captured["profile"]["think"] is False
    assert "7759" in str(captured["prompt"])
    assert "backend second-opinion model required" in payload["guardrails"]


def test_second_opinion_prompt_is_capped_for_ui_latency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_BACKEND_BASE_URL", BACKEND_LANE_URL)
    monkeypatch.setenv("AI_BACKEND_MODEL", BACKEND_LANE_MODEL)

    long_context = [
        {
            "source_id": f"source-{index}",
            "title": f"Source {index}",
            "excerpt": f"claim detail {index} " + ("x" * 2000),
        }
        for index in range(1, 8)
    ]
    captured: dict[str, object] = {}

    def fake_generate_response_result(*, base_url, profile, prompt, timeout_seconds, seed=None):
        del base_url, timeout_seconds, seed
        captured["profile"] = profile
        captured["prompt"] = prompt
        return {"response_text": "Concise backend second opinion."}

    monkeypatch.setattr(
        hal_orchestrator,
        "require_lane_runtime",
        make_require_lane_runtime_mock(expected_alias="chat_second_opinion"),
    )
    monkeypatch.setattr(hal_orchestrator, "generate_response_result", fake_generate_response_result)
    monkeypatch.setattr(hal_orchestrator, "retrieve_relevant_context", lambda question: long_context)
    monkeypatch.setattr(hal_orchestrator, "get_live_financial_context", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_hardware_snippets", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_softdent_aggregate_snippets", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_live_report_snippets", lambda question: [])
    monkeypatch.setattr(
        hal_orchestrator,
        "get_controlled_patient_context",
        lambda question: {"matched": False, "snippets": [], "narrative": ""},
    )

    hal_orchestrator.answer_hal_second_opinion_question(
        question="Give me a deeper second opinion on collections risk.",
        actor="hal_operator",
        summary={"large": "y" * 5000},
    )

    prompt = str(captured["prompt"])
    assert "Answer immediately in no more than 60 words" in prompt
    assert "Do not explain your steps" in prompt
    assert "Source 2" in prompt
    assert "Source 3" not in prompt
    assert "claim detail 1 " + ("x" * 400) not in prompt
    assert captured["profile"]["num_predict"] == hal_orchestrator.SECOND_OPINION_NUM_PREDICT
    assert captured["profile"]["think"] is False


def test_patient_claims_second_opinion_returns_immediate_context_check(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_model_called(*args, **kwargs):
        raise AssertionError("Patient/claims second opinion should not wait on backend model generation")

    def fail_if_broad_context_called(*args, **kwargs):
        raise AssertionError("Patient/claims second opinion should use slim local context")

    monkeypatch.setattr(hal_orchestrator, "require_lane_runtime", fail_if_model_called)
    monkeypatch.setattr(hal_orchestrator, "generate_response_result", fail_if_model_called)
    monkeypatch.setattr(hal_orchestrator, "retrieve_relevant_context", fail_if_broad_context_called)
    monkeypatch.setattr(hal_orchestrator, "get_live_financial_context", fail_if_broad_context_called)
    monkeypatch.setattr(hal_orchestrator, "compile_hardware_snippets", fail_if_broad_context_called)
    monkeypatch.setattr(hal_orchestrator, "compile_softdent_aggregate_snippets", fail_if_broad_context_called)
    monkeypatch.setattr(hal_orchestrator, "compile_live_report_snippets", fail_if_broad_context_called)
    monkeypatch.setattr(
        hal_orchestrator,
        "load_softdent_claim_rows",
        lambda: [
            {
                "PatientName": "John Doe",
                "ClaimId": "CLM-2026-1002",
                "ClaimStatus": "Pending Review",
                "Payer": "Delta Dental",
                "Procedure": "Core buildup tooth #30",
                "ServiceDate": "2026-06-12",
                "DenialReason": "Awaiting supplemental narrative and supporting clinical notes.",
                "ClaimAmount": 148.0,
            }
        ],
    )
    monkeypatch.setattr(
        hal_orchestrator,
        "get_controlled_patient_context",
        lambda question: {
            "matched": True,
            "snippets": [{"source_id": "claim-1", "title": "Claim 1", "excerpt": "Pending review claim evidence"}],
            "narrative": "",
            "summary_fields": {
                "patient_name": "John Doe",
                "claim_count": 1,
                "total_claim_amount": 148,
                "primary_claim_status": "Pending Review",
            },
        },
    )

    payload = hal_orchestrator.answer_hal_second_opinion_question(
        question="Which insurance claims are still pending?",
        actor="hal_operator",
    )

    assert payload["mode"] == "local-rag-phase-1:second-opinion"
    assert "CLM-2026-1002" in payload["answer"]
    assert "Pending Review" in payload["answer"]
    assert "Delta Dental" in payload["answer"]
    assert "John Doe" in payload["answer"]
    assert payload["local_ai_unavailable"] is None
    assert "deterministic local claims review used" in payload["guardrails"]
    assert "local SoftDent export rows reviewed" in payload["guardrails"]
    assert "no external submission performed" in payload["guardrails"]
    assert "backend model not required for this deterministic claims answer" in payload["guardrails"]
    assert "backend second-opinion model required" not in payload["guardrails"]
    assert "no deterministic fallback when backend unavailable" not in payload["guardrails"]
    retrieved_excerpt = str(payload["retrieved_context"][0].get("excerpt", ""))
    assert "PatientName,MRN,ClaimId" not in retrieved_excerpt
    assert "John Doe" in retrieved_excerpt
    audit = get_hal_audit(payload["audit_id"])
    assert audit is not None
    assert "CLM-2026-1002" in audit["response_summary"]
    assert len(audit["response_summary"]) <= 180


def test_patient_specific_claims_second_opinion_may_include_named_patient(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_model_called(*args, **kwargs):
        raise AssertionError("Patient-specific second opinion should not wait on backend model generation")

    monkeypatch.setattr(hal_orchestrator, "require_lane_runtime", fail_if_model_called)
    monkeypatch.setattr(hal_orchestrator, "generate_response_result", fail_if_model_called)
    monkeypatch.setattr(
        hal_orchestrator,
        "load_softdent_claim_rows",
        lambda: [
            {
                "PatientName": "John Doe",
                "ClaimId": "CLM-2026-1002",
                "ClaimStatus": "Pending Review",
                "Payer": "Delta Dental",
                "Procedure": "Core buildup tooth #30",
                "ServiceDate": "2026-06-12",
                "DenialReason": "Awaiting supplemental narrative and supporting clinical notes.",
                "ClaimAmount": 148.0,
            }
        ],
    )
    monkeypatch.setattr(
        hal_orchestrator,
        "get_controlled_patient_context",
        lambda question: {
            "matched": True,
            "snippets": [{"source_id": "claim-1", "title": "Claim 1", "excerpt": "Pending review claim evidence"}],
            "narrative": "",
            "summary_fields": {
                "patient_name": "John Doe",
                "claim_count": 1,
                "total_claim_amount": 148,
                "primary_claim_status": "Pending Review",
            },
        },
    )

    payload = hal_orchestrator.answer_hal_second_opinion_question(
        question="What open claims does patient John Doe have?",
        actor="hal_operator",
    )

    assert payload["mode"] == "local-rag-phase-1:second-opinion"
    assert "John Doe" in payload["answer"]
    assert "CLM-2026-1002" in payload["answer"]
    assert "deterministic local claims review used" in payload["guardrails"]
    assert "authorized internal office context" in payload["guardrails"]
    audit = get_hal_audit(payload["audit_id"])
    assert audit is not None
    assert "CLM-2026-1002" in audit["response_summary"]
    assert len(audit["response_summary"]) <= 180


def test_hal_chat_stays_deterministic_without_local_ai_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_generate(*args, **kwargs):
        raise AssertionError("HAL chat must not call generate_response_result")

    monkeypatch.setattr(hal_orchestrator, "generate_response_result", fail_generate)
    monkeypatch.setattr(hal_orchestrator, "retrieve_relevant_context", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "get_live_financial_context", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_hardware_snippets", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_softdent_aggregate_snippets", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_live_report_snippets", lambda question: [])
    monkeypatch.setattr(
        hal_orchestrator,
        "get_controlled_patient_context",
        lambda question: {"matched": False, "snippets": [], "narrative": ""},
    )

    payload = hal_orchestrator.answer_hal_question(
        question="What matters most this morning?",
        actor="hal_operator",
    )

    assert payload["mode"] == "local-rag-phase-1"
    assert "deterministic server facts first" in payload["guardrails"]


def test_coder_profile_still_resolves_to_backend_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_BACKEND_BASE_URL", "http://127.0.0.1:11435")
    monkeypatch.setenv("AI_BACKEND_MODEL", "qwen3:30b")

    assert config.resolve_profile_base_url("coder") == "http://127.0.0.1:11435"
    assert config.get_model_for_profile_alias("coder") == "qwen3:30b"


def test_hal_chat_still_resolves_to_frontend_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FRONTEND_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("AI_FRONTEND_MODEL", "mistral-small3.1:24b")

    assert config.resolve_profile_base_url("chat") == "http://127.0.0.1:11434"
    assert config.get_model_for_profile_alias("chat") == "mistral-small3.1:24b"


def test_second_opinion_backend_unavailable_returns_explicit_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_require_lane_runtime(alias, *, purpose):
        raise LocalAIConfigError(
            "Local AI runtime unavailable for HAL second opinion. "
            "Lane=backend, model=qwen3:30b, base_url=http://127.0.0.1:11435. connection refused"
        )

    monkeypatch.setattr(hal_orchestrator, "require_lane_runtime", fake_require_lane_runtime)
    monkeypatch.setattr(hal_orchestrator, "generate_response_result", lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not generate")))
    monkeypatch.setattr(hal_orchestrator, "retrieve_relevant_context", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "get_live_financial_context", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_hardware_snippets", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_softdent_aggregate_snippets", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_live_report_snippets", lambda question: [])
    monkeypatch.setattr(
        hal_orchestrator,
        "get_controlled_patient_context",
        lambda question: {"matched": False, "snippets": [], "narrative": ""},
    )

    payload = hal_orchestrator.answer_hal_second_opinion_question(
        question="Give me a deeper second opinion on collections risk.",
        actor="hal_operator",
    )

    assert payload["answer"].startswith("Second opinion unavailable.")
    assert payload["local_ai_unavailable"] is not None
    assert "Backend local AI lane unavailable" in payload["local_ai_unavailable"]
    assert "no deterministic fallback when backend unavailable" in payload["guardrails"]
    assert payload["answer"] != payload.get("narrative")
    assert "deterministic server facts first" not in payload["answer"]
    assert payload["mode"] == "local-rag-phase-1:second-opinion"


def test_second_opinion_unavailable_does_not_use_frontend_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FRONTEND_BASE_URL", FRONTEND_LANE_URL)
    monkeypatch.setenv("AI_BACKEND_BASE_URL", BACKEND_LANE_URL)

    def fake_require_lane_runtime(alias, *, purpose):
        raise LocalAIConfigError(
            f"Local AI runtime unavailable for HAL second opinion. "
            f"Lane=backend, model={BACKEND_LANE_MODEL}, base_url={BACKEND_LANE_URL}. connection refused"
        )

    def fail_if_frontend_lane(**kwargs):
        base_url = kwargs.get("base_url", "")
        raise AssertionError(f"Second opinion must not generate via frontend lane: {base_url}")

    monkeypatch.setattr(hal_orchestrator, "require_lane_runtime", fake_require_lane_runtime)
    monkeypatch.setattr(hal_orchestrator, "generate_response_result", fail_if_frontend_lane)
    monkeypatch.setattr(hal_orchestrator, "retrieve_relevant_context", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "get_live_financial_context", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_hardware_snippets", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_softdent_aggregate_snippets", lambda question: [])
    monkeypatch.setattr(hal_orchestrator, "compile_live_report_snippets", lambda question: [])
    monkeypatch.setattr(
        hal_orchestrator,
        "get_controlled_patient_context",
        lambda question: {"matched": False, "snippets": [], "narrative": ""},
    )

    payload = hal_orchestrator.answer_hal_second_opinion_question(
        question="Give me a deeper second opinion on collections risk.",
        actor="hal_operator",
    )

    assert payload["answer"].startswith("Second opinion unavailable.")
    assert payload["local_ai_unavailable"] is not None


def test_deterministic_claims_second_opinion_uses_internal_staff_language(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hal_orchestrator, "require_lane_runtime", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no model")))
    monkeypatch.setattr(hal_orchestrator, "generate_response_result", lambda **kwargs: (_ for _ in ()).throw(AssertionError("no model")))
    monkeypatch.setattr(
        hal_orchestrator,
        "load_softdent_claim_rows",
        lambda: [
            {
                "PatientName": "John Doe",
                "ClaimId": "CLM-2026-1002",
                "ClaimStatus": "Pending Review",
                "Payer": "Delta Dental",
                "Procedure": "Core buildup tooth #30",
                "ServiceDate": "2026-06-12",
                "ClaimAmount": 148.0,
            }
        ],
    )
    monkeypatch.setattr(
        hal_orchestrator,
        "get_controlled_patient_context",
        lambda question: {"matched": True, "snippets": [], "narrative": "", "summary_fields": {"patient_name": "John Doe"}},
    )

    payload = hal_orchestrator.answer_hal_second_opinion_question(
        question="What open claims does patient John Doe have?",
        actor="hal_operator",
    )

    assert "Next action:" in payload["answer"]
    assert "Reason:" in payload["answer"]
    assert "John Doe" in payload["answer"]
    assert "no external submission performed" in payload["guardrails"]
    assert "has been submitted" not in payload["answer"].lower()


def test_broad_office_second_opinion_may_name_patients_when_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hal_orchestrator, "require_lane_runtime", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no model")))
    monkeypatch.setattr(hal_orchestrator, "generate_response_result", lambda **kwargs: (_ for _ in ()).throw(AssertionError("no model")))
    monkeypatch.setattr(
        hal_orchestrator,
        "load_softdent_claim_rows",
        lambda: [
            {
                "PatientName": "John Doe",
                "ClaimId": "CLM-1",
                "ClaimStatus": "Open",
                "Procedure": "Crown",
                "ClaimAmount": 100.0,
            },
            {
                "PatientName": "John Doe",
                "ClaimId": "CLM-2",
                "ClaimStatus": "Open",
                "Procedure": "Buildup",
                "ClaimAmount": 50.0,
            },
            {
                "PatientName": "Jane Smith",
                "ClaimId": "CLM-3",
                "ClaimStatus": "Open",
                "Procedure": "Prophy",
                "ClaimAmount": 75.0,
            },
        ],
    )
    monkeypatch.setattr(
        hal_orchestrator,
        "get_controlled_patient_context",
        lambda question: {"matched": False, "snippets": [], "narrative": ""},
    )

    payload = hal_orchestrator.answer_hal_second_opinion_question(
        question="Which patients have multiple open insurance claims?",
        actor="hal_operator",
    )

    assert "John Doe" in payload["answer"]
    assert "multiple open claims" in payload["answer"].lower()
    assert "PatientName,MRN,ClaimId" not in payload["answer"]
