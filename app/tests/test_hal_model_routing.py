from __future__ import annotations

import pytest

from app.ai_local_config import get_backend_model_name, get_hal_fast_model_name
from app.hal import orchestrator as hal_orchestrator


@pytest.fixture(autouse=True)
def enable_hal_ask_model_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAL_ASK_MODEL_ROUTING", "1")


def test_generic_help_is_deterministic_without_model_call(monkeypatch: pytest.MonkeyPatch) -> None:
    model_called = {"value": False}

    def fake_generate(**kwargs):
        del kwargs
        model_called["value"] = True
        return "should not run", None

    monkeypatch.setattr(hal_orchestrator, "_generate_profile_answer", fake_generate)
    payload = hal_orchestrator.answer_hal_question(question="can you help me", actor="hal_operator")

    assert model_called["value"] is False
    assert payload["answer_lane"] == "deterministic"
    assert payload.get("model_used") is None
    assert payload["escalated"] is False


def test_routine_office_prompt_routes_to_fast_model(monkeypatch: pytest.MonkeyPatch) -> None:
    context_bundle = {
        "state": {"action_items": ["Review denied claims"]},
        "patient_context": {"matched": False},
        "sanitized": {"findings": []},
        "sanitized_question": "What needs attention today?",
        "hardware_context": [],
        "hardware_review_actions": [],
        "softdent_aggregate_context": [],
        "live_report_context": [],
        "combined_context": [],
        "operating_picture": {"summary": ""},
    }
    calls: list[str] = []

    def fake_collect(**kwargs):
        del kwargs
        return context_bundle

    def fake_generate(*, profile_alias: str, prompt: str, num_predict_cap: int, timeout_override=None):
        del prompt, num_predict_cap, timeout_override
        calls.append(profile_alias)
        if profile_alias == "chat_fast":
            return "Review denied claims first, then confirm today's imports.", None
        return None, "unexpected profile"

    monkeypatch.setattr(hal_orchestrator, "_collect_hal_question_context", fake_collect)
    monkeypatch.setattr(hal_orchestrator, "_generate_profile_answer", fake_generate)
    monkeypatch.setenv("HAL_ENABLE_FAST_MODEL", "1")

    payload = hal_orchestrator.answer_hal_question(
        question="What needs attention today?",
        actor="hal_operator",
    )

    assert "chat_fast" in calls
    assert payload["answer_lane"] == "fast_model"
    assert payload["model_used"] == get_hal_fast_model_name()
    assert payload["escalated"] is False


def test_complex_patient_prompt_skips_fast_model(monkeypatch: pytest.MonkeyPatch) -> None:
    context_bundle = {
        "state": {},
        "patient_context": {"matched": True, "narrative": "Patient claim review context."},
        "sanitized": {"findings": []},
        "sanitized_question": "Draft insurance narrative for denied claim",
        "hardware_context": [],
        "hardware_review_actions": [],
        "softdent_aggregate_context": [],
        "live_report_context": [],
        "combined_context": [],
        "operating_picture": {"summary": ""},
    }
    calls: list[str] = []

    def fake_collect(**kwargs):
        del kwargs
        return context_bundle

    def fake_generate(*, profile_alias: str, prompt: str, num_predict_cap: int, timeout_override=None):
        del prompt, num_predict_cap, timeout_override
        calls.append(profile_alias)
        if profile_alias == "chat":
            return "Primary model narrative draft.", None
        return None, "unexpected profile"

    monkeypatch.setattr(hal_orchestrator, "_collect_hal_question_context", fake_collect)
    monkeypatch.setattr(hal_orchestrator, "_generate_profile_answer", fake_generate)
    monkeypatch.setenv("HAL_ENABLE_FAST_MODEL", "1")

    payload = hal_orchestrator.answer_hal_question(
        question="Draft insurance narrative for denied claim",
        actor="hal_operator",
    )

    assert "chat_fast" not in calls
    assert payload["answer_lane"] == "deterministic"
    assert "Patient claim review context." in payload["answer"]


def test_primary_escalates_to_fallback_only_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    context_bundle = {
        "state": {},
        "patient_context": {"matched": False},
        "sanitized": {"findings": []},
        "sanitized_question": "Explain conflicting payer facts for claim CLM-1001",
        "hardware_context": [],
        "hardware_review_actions": [],
        "softdent_aggregate_context": [],
        "live_report_context": [],
        "combined_context": [],
        "operating_picture": {"summary": ""},
    }

    def fake_collect(**kwargs):
        del kwargs
        return context_bundle

    def fake_generate(*, profile_alias: str, prompt: str, num_predict_cap: int, timeout_override=None):
        del prompt, num_predict_cap, timeout_override
        if profile_alias == "chat":
            return "[NEEDS_ESCALATION]", None
        if profile_alias == "chat_second_opinion":
            return "Fallback review answer.", None
        return None, "unexpected profile"

    monkeypatch.setattr(hal_orchestrator, "_collect_hal_question_context", fake_collect)
    monkeypatch.setattr(hal_orchestrator, "_generate_profile_answer", fake_generate)
    monkeypatch.setenv("HAL_ENABLE_FAST_MODEL", "0")

    payload = hal_orchestrator.answer_hal_question(
        question="Explain conflicting payer facts for claim CLM-1001",
        actor="hal_operator",
    )

    assert payload["answer"] == "Fallback review answer."
    assert payload["answer_lane"] == "fallback"
    assert payload["escalated"] is True
    assert payload["model_used"] == get_backend_model_name()


def test_short_primary_answer_does_not_auto_escalate(monkeypatch: pytest.MonkeyPatch) -> None:
    context_bundle = {
        "state": {},
        "patient_context": {"matched": False},
        "sanitized": {"findings": []},
        "sanitized_question": "Explain conflicting payer facts for claim CLM-1001",
        "hardware_context": [],
        "hardware_review_actions": [],
        "softdent_aggregate_context": [],
        "live_report_context": [],
        "combined_context": [],
        "operating_picture": {"summary": ""},
    }

    def fake_collect(**kwargs):
        del kwargs
        return context_bundle

    def fake_generate(*, profile_alias: str, prompt: str, num_predict_cap: int, timeout_override=None):
        del prompt, num_predict_cap, timeout_override
        if profile_alias == "chat":
            return "Short but usable answer.", None
        raise AssertionError("30B fallback should not run for a short usable primary answer")

    monkeypatch.setattr(hal_orchestrator, "_collect_hal_question_context", fake_collect)
    monkeypatch.setattr(hal_orchestrator, "_generate_profile_answer", fake_generate)
    monkeypatch.setenv("HAL_ENABLE_FAST_MODEL", "0")

    payload = hal_orchestrator.answer_hal_question(
        question="Explain conflicting payer facts for claim CLM-1001",
        actor="hal_operator",
    )

    assert payload["answer"] == "Short but usable answer."
    assert payload["answer_lane"] == "primary"
    assert payload["escalated"] is False


def test_ar_availability_uses_deterministic_status_not_model(monkeypatch: pytest.MonkeyPatch) -> None:
    model_called = {"value": False}

    def fake_generate(**kwargs):
        del kwargs
        model_called["value"] = True
        return "The total A/R is $9,765.", None

    monkeypatch.setattr(hal_orchestrator, "_generate_profile_answer", fake_generate)
    monkeypatch.setattr(
        hal_orchestrator,
        "_build_ar_availability_status_answer",
        lambda: "SoftDent DAYSHEET A/R is not imported yet.",
    )

    payload = hal_orchestrator.answer_hal_question(
        question="Is A/R available from the DAYSHEET?",
        actor="hal_operator",
    )

    assert model_called["value"] is False
    assert payload["answer_lane"] == "deterministic"
    assert "$0" not in payload["answer"]
    assert "not imported yet" in payload["answer"].lower()


def test_no_235b_or_cloud_models_used(monkeypatch: pytest.MonkeyPatch) -> None:
    context_bundle = {
        "state": {},
        "patient_context": {"matched": False},
        "sanitized": {"findings": []},
        "sanitized_question": "Summarize today's tasks",
        "hardware_context": [],
        "hardware_review_actions": [],
        "softdent_aggregate_context": [],
        "live_report_context": [],
        "combined_context": [],
        "operating_picture": {"summary": ""},
    }

    def fake_collect(**kwargs):
        del kwargs
        return context_bundle

    def fake_generate(*, profile_alias: str, prompt: str, num_predict_cap: int, timeout_override=None):
        del prompt, num_predict_cap, timeout_override
        if profile_alias == "chat_fast":
            return "Today's tasks summary.", None
        return None, "unexpected profile"

    monkeypatch.setattr(hal_orchestrator, "_collect_hal_question_context", fake_collect)
    monkeypatch.setattr(hal_orchestrator, "_generate_profile_answer", fake_generate)

    payload = hal_orchestrator.answer_hal_question(
        question="Summarize today's tasks",
        actor="hal_operator",
    )

    model_used = str(payload.get("model_used") or "")
    assert "235b" not in model_used.lower()
    assert "cloud" not in model_used.lower()
    assert payload["answer_lane"] == "fast_model"


def test_fast_model_prompt_excludes_dashboard_diagnostics() -> None:
    prompt = hal_orchestrator._build_fast_model_prompt(
        sanitized_question="Prepare morning huddle",
        minimal_facts="Open tasks: Review claims",
    )
    assert "QuickBooks SDK" not in prompt
    assert "README chunk" not in prompt
    assert "local read-only dental office manager assistant" in prompt.lower()
    assert "Open tasks: Review claims" in prompt
