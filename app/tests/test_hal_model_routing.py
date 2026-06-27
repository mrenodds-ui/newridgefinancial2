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
        raise AssertionError("14B fallback should not run for a short usable primary answer")

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
        "state": {"action_items": ["Review denied claims"]},
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


def test_sanitize_staff_facing_answer_strips_prompt_artifacts() -> None:
    raw = (
        "We are given: \"Verified local context: No additional verified context retrieved.\" "
        "Since there is no verified context provided, here is the practical answer.\n"
        "According to the instructions: stay local.\n"
        "Use the answer above as the current staff recommendation.\n"
        "No follow-up question is required yet."
    )
    cleaned = hal_orchestrator._sanitize_staff_facing_answer(raw)
    assert "We are given" not in cleaned
    assert "According to the instructions" not in cleaned
    assert "Verified local context" not in cleaned
    assert "No additional verified context retrieved" not in cleaned
    assert "Use the answer above" not in cleaned
    assert "No follow-up question is required yet" not in cleaned


def _empty_context_bundle(question: str) -> dict[str, object]:
    return {
        "state": {"action_items": []},
        "patient_context": {"matched": False},
        "sanitized": {"findings": [], "sanitized_text": question},
        "sanitized_question": question,
        "hardware_context": [],
        "hardware_review_actions": [],
        "softdent_aggregate_context": [],
        "live_report_context": [],
        "combined_context": [],
        "operating_picture": {"summary": ""},
    }


def _docs_only_context_bundle(question: str) -> dict[str, object]:
    bundle = _empty_context_bundle(question)
    bundle["combined_context"] = [
        {
            "source_id": "readme-chunk-42",
            "title": "README chunk 42",
            "category": "documentation",
            "excerpt": "HAL dashboard route docs explain how the app navigation works.",
        },
        {
            "source_id": "dashboard-docs",
            "title": "Dashboard documentation",
            "category": "documentation",
            "excerpt": "Automatically augments answers with live SoftDent aggregate summaries when the question asks about production.",
        },
    ]
    return bundle


def test_huddle_docs_only_context_returns_no_context_checklist(monkeypatch: pytest.MonkeyPatch) -> None:
    question = "prepare a short morning huddle summary"
    monkeypatch.setattr(
        hal_orchestrator,
        "_collect_hal_question_context",
        lambda **kwargs: _docs_only_context_bundle(question),
    )

    def fail_generate(**kwargs):
        del kwargs
        raise AssertionError("README/docs-only huddle prompt should not call a model")

    monkeypatch.setattr(hal_orchestrator, "_generate_profile_answer", fail_generate)

    payload = hal_orchestrator.answer_hal_question(question=question, actor="hal_operator")

    assert payload["answer_lane"] == "deterministic"
    assert payload["answer"].startswith("I do not have a verified office snapshot yet.")
    assert "README" not in payload["answer"]
    assert "dashboard route docs" not in payload["answer"]
    assert "Automatically augments answers" not in payload["answer"]


def test_narrative_docs_only_context_returns_missing_claim_facts(monkeypatch: pytest.MonkeyPatch) -> None:
    question = "help me think through an insurance narrative for a denied crown claim using available local facts"
    monkeypatch.setattr(
        hal_orchestrator,
        "_collect_hal_question_context",
        lambda **kwargs: _docs_only_context_bundle(question),
    )

    def fail_generate(**kwargs):
        del kwargs
        raise AssertionError("Docs-only narrative prompt should not use docs as model context")

    monkeypatch.setattr(hal_orchestrator, "_generate_profile_answer", fail_generate)

    payload = hal_orchestrator.answer_hal_question(question=question, actor="hal_operator")

    assert payload["answer_lane"] == "deterministic"
    assert "I do not have verified claim facts" in payload["answer"]
    assert "claim status and payer" in payload["answer"]
    assert "README" not in payload["answer"]
    assert "dashboard route docs" not in payload["answer"]
    assert "submit" in payload["answer"]
    assert "write back to SoftDent" in payload["answer"]


def test_narrative_with_real_claim_facts_routes_to_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    question = "help me think through an insurance narrative for a denied crown claim using available local facts"
    claim_fact = {
        "source_id": "softdent-claims-summary",
        "title": "SoftDent claims retrieval",
        "category": "softdent_tool",
        "excerpt": "PatientName=John Doe; ClaimId=CLM-1001; ClaimStatus=Denied; Payer=Delta Dental; Procedure=Crown.",
    }
    bundle = _empty_context_bundle(question)
    bundle["combined_context"] = [
        {
            "source_id": "readme-chunk-42",
            "title": "README chunk 42",
            "category": "documentation",
            "excerpt": "HAL dashboard route docs explain how the app navigation works.",
        },
        claim_fact,
    ]
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(hal_orchestrator, "_collect_hal_question_context", lambda **kwargs: bundle)

    def fake_generate(*, profile_alias: str, prompt: str, num_predict_cap: int, timeout_override=None):
        del num_predict_cap, timeout_override
        calls.append((profile_alias, prompt))
        if profile_alias == "chat":
            return "Use the denied crown claim facts to prepare a local draft for human review.", None
        return None, "unexpected profile"

    monkeypatch.setattr(hal_orchestrator, "_generate_profile_answer", fake_generate)

    payload = hal_orchestrator.answer_hal_question(question=question, actor="hal_operator")

    assert payload["answer_lane"] == "primary"
    assert payload["model_used"]
    assert calls[0][0] == "chat"
    assert "ClaimStatus=Denied" in calls[0][1]
    assert "README chunk" not in calls[0][1]
    assert "dashboard route docs" not in calls[0][1]


def test_routine_prompt_without_context_avoids_model_and_artifacts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        hal_orchestrator,
        "_collect_hal_question_context",
        lambda **kwargs: _empty_context_bundle("what needs attention today"),
    )

    def fail_generate(**kwargs):
        del kwargs
        raise AssertionError("No model should be called for a routine prompt with no verified context")

    monkeypatch.setattr(hal_orchestrator, "_generate_profile_answer", fail_generate)

    payload = hal_orchestrator.answer_hal_question(
        question="what needs attention today",
        actor="hal_operator",
    )

    answer = payload["answer"]
    assert payload["answer_lane"] == "deterministic"
    assert "We are given" not in answer
    assert "According to the instructions" not in answer
    assert "No additional verified context retrieved" not in answer
    assert "I do not have a verified office snapshot yet." in answer
    assert "DAYSHEET" in answer
    assert "blocked claims" in answer
    assert "missing SoftDent exports" in answer
    assert "drafts waiting for review" in answer
    assert "local office tasks" in answer
    assert len(answer) < 400


def test_routine_no_context_answer_is_concise_office_manager_voice(monkeypatch: pytest.MonkeyPatch) -> None:
    for question in ("morning huddle", "summarize today's tasks", "explain this status"):
        monkeypatch.setattr(
            hal_orchestrator,
            "_collect_hal_question_context",
            lambda **kwargs: _empty_context_bundle(question),
        )
        payload = hal_orchestrator.answer_hal_question(question=question, actor="hal_operator")
        assert payload["answer_lane"] == "deterministic", question
        assert payload["answer"].startswith("I do not have a verified office snapshot yet."), question


def test_generic_help_remains_deterministic_and_concise() -> None:
    payload = hal_orchestrator.answer_hal_question(question="can you help me", actor="hal_operator")
    assert payload["answer_lane"] == "deterministic"
    assert payload["answer"].startswith("Yes.")
    assert "write back to SoftDent" in payload["answer"]
    assert "We are given" not in payload["answer"]


def _ar_question_bundle_with_qb_diagnostics(question: str) -> dict[str, object]:
    qb_diagnostic = {
        "source_id": "qb-ar-live",
        "title": "QuickBooks A/R live status",
        "category": "live_report",
        "excerpt": (
            "QuickBooks ar SDK summary is currently unavailable: QuickBooks SDK subprocess failed: "
            "(-2147221164, 'Exception occurred.', (0, 'QBXMLRP2.RequestProcessor.2', ...))"
        ),
    }
    bundle = _empty_context_bundle(question)
    bundle["live_report_context"] = [qb_diagnostic]
    bundle["combined_context"] = [qb_diagnostic]
    return bundle


def test_ar_availability_answer_hides_quickbooks_sdk_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    question = "is A/R available"
    monkeypatch.setattr(
        hal_orchestrator,
        "_collect_hal_question_context",
        lambda **kwargs: _ar_question_bundle_with_qb_diagnostics(question),
    )
    monkeypatch.setattr(
        hal_orchestrator,
        "_build_ar_availability_status_answer",
        lambda: (
            "SoftDent DAYSHEET A/R is not imported yet.\n"
            "A/R balances are unavailable until a current SoftDent Daily End-of-Day / DAYSHEET report is imported.\n"
            + hal_orchestrator._build_ar_import_next_steps()
        ),
    )

    def fail_generate(**kwargs):
        del kwargs
        raise AssertionError("A/R availability prompt should not call a model")

    monkeypatch.setattr(hal_orchestrator, "_generate_profile_answer", fail_generate)

    payload = hal_orchestrator.answer_hal_question(question=question, actor="hal_operator")
    answer = payload["answer"]

    assert payload["answer_lane"] == "deterministic"
    assert "QuickBooks" not in answer
    assert "SDK" not in answer
    assert "QBXML" not in answer
    assert "source-health" not in answer.lower()
    # The reassurance line ("not $0") is allowed; a fabricated zero balance is not.
    assert "is $0" not in answer
    assert "$0.00" not in answer
    assert "SoftDent DAYSHEET A/R is not imported yet." in answer
    assert "Daily End-of-Day" in answer
    assert "Missing A/R is unavailable, not $0." in answer
    # The raw diagnostic is still retained in retrieved_context metadata (Advanced-only).
    assert any(
        "QBXML" in str(item.get("excerpt") or "")
        for item in payload["retrieved_context"]
        if isinstance(item, dict)
    )


def test_ar_import_next_steps_names_daysheet_source_and_not_zero() -> None:
    text = hal_orchestrator._build_ar_import_next_steps()
    assert "SoftDent Daily End-of-Day / DAYSHEET report" in text
    assert "daily_end_of_day import folder" in text
    assert "Missing A/R is unavailable, not $0." in text


def test_missing_exports_answer_excludes_qb_report_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    question = "which exports are missing"
    monkeypatch.setattr(
        hal_orchestrator,
        "_collect_hal_question_context",
        lambda **kwargs: _ar_question_bundle_with_qb_diagnostics(question),
    )
    monkeypatch.setattr(
        hal_orchestrator,
        "_build_missing_exports_status_answer",
        lambda: "Missing or unavailable SoftDent exports: Claims Export.",
    )

    payload = hal_orchestrator.answer_hal_question(question=question, actor="hal_operator")
    answer = payload["answer"]

    assert payload["answer_lane"] == "deterministic"
    assert "QBXML" not in answer
    assert "SDK" not in answer
    assert "QuickBooks ar SDK summary" not in answer
    assert "Missing or unavailable SoftDent exports" in answer
