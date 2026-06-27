from __future__ import annotations

import pytest

from app.hal import orchestrator as hal_orchestrator


@pytest.fixture(autouse=True)
def enable_hal_ask_model_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAL_ASK_MODEL_ROUTING", "1")


def test_should_escalate_primary_answer_on_empty_or_marker() -> None:
    assert hal_orchestrator._should_escalate_primary_answer("") is True
    assert hal_orchestrator._should_escalate_primary_answer("   ") is True
    assert hal_orchestrator._should_escalate_primary_answer("[NEEDS_ESCALATION]") is True
    assert hal_orchestrator._should_escalate_primary_answer("cannot determine from the provided context") is True


def test_should_not_escalate_primary_answer_for_normal_response() -> None:
    answer = (
        "Latest daily gross production is $7,759 based on verified SoftDent metrics. "
        "Next step: review the provider summary with billing."
    )
    assert hal_orchestrator._should_escalate_primary_answer(answer) is False


def test_should_not_escalate_primary_answer_only_because_it_is_long() -> None:
    answer = "Verified context supports the recommendation. " * 20
    assert hal_orchestrator._should_escalate_primary_answer(answer) is False


def test_answer_hal_question_escalates_from_24b_to_30b(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAL_ENABLE_FAST_MODEL", "0")
    question = "Walk me through the denied crown claim appeal reasoning"
    context_bundle = {
        "state": {},
        "patient_context": {"matched": False},
        "sanitized": {"findings": []},
        "sanitized_question": question,
        "hardware_context": [],
        "hardware_review_actions": [],
        "softdent_aggregate_context": [],
        "live_report_context": [],
        "combined_context": [],
        "operating_picture": {"summary": "Operating picture"},
    }

    def fake_collect(**kwargs):
        del kwargs
        return context_bundle

    def fake_generate(*, profile_alias: str, prompt: str, num_predict_cap: int, timeout_override=None):
        del prompt, num_predict_cap, timeout_override
        if profile_alias == "chat":
            return "[NEEDS_ESCALATION]", None
        if profile_alias == "chat_second_opinion":
            return "Escalated deeper review answer for staff.", None
        return None, "unexpected profile"

    monkeypatch.setattr(hal_orchestrator, "_collect_hal_question_context", fake_collect)
    monkeypatch.setattr(hal_orchestrator, "_generate_profile_answer", fake_generate)

    payload = hal_orchestrator.answer_hal_question(
        question=question,
        actor="hal_operator",
    )

    assert payload["answer"] == "Escalated deeper review answer for staff."
    assert payload["voice_profile"]["label"] == "HAL needed a deeper review"
    assert payload["mode"].endswith(":deeper-review")
    assert payload["answer_lane"] == "fallback"
    assert payload["escalated"] is True


def test_answer_hal_question_falls_back_to_deterministic_when_models_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hal_orchestrator, "_try_hal_model_answer_with_escalation", lambda **kwargs: None)

    payload = hal_orchestrator.answer_hal_question(
        question="Summarize the top two action items",
        actor="hal_operator",
    )

    assert payload["mode"] == hal_orchestrator.HAL_MODE
    assert payload["answer"]
    assert "deterministic server facts first" in payload["guardrails"]


def test_generic_help_returns_concise_capability_answer() -> None:
    payload = hal_orchestrator.answer_hal_question(
        question="can you help me",
        actor="hal_operator",
    )

    assert payload["mode"].endswith(":generic-help")
    assert payload["answer_lane"] == "deterministic"
    assert payload["answer"].startswith("Yes.")
    assert "local office tasks" in payload["answer"]
    assert "read-only" in payload["answer"].lower()
    assert "write back to SoftDent" in payload["answer"]
    assert "README chunk" not in payload["answer"]
    assert "Relevant context" not in payload["answer"]
    assert "Key approved guidance" not in payload["answer"]
    assert payload["retrieved_context"] == []


def test_generic_help_variants_use_same_path() -> None:
    for question in ("what can you do", "help", "how can you help the office"):
        payload = hal_orchestrator.answer_hal_question(question=question, actor="hal_operator")
        assert payload["mode"].endswith(":generic-help"), question
        assert "README chunk" not in payload["answer"], question


def test_normal_question_does_not_surface_readme_chunk_ids_in_main_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hal_orchestrator, "_try_hal_model_answer_with_escalation", lambda **kwargs: None)
    monkeypatch.setattr(
        hal_orchestrator,
        "_collect_hal_question_context",
        lambda **kwargs: {
            "state": {"action_items": []},
            "patient_context": {"matched": False},
            "sanitized": {"findings": [], "sanitized_text": "What is today's production?"},
            "sanitized_question": "What is today's production?",
            "hardware_context": [],
            "hardware_review_actions": [],
            "softdent_aggregate_context": [
                {
                    "source_id": "softdent-live-production",
                    "title": "SoftDent production",
                    "category": "softdent_aggregate",
                    "excerpt": "Daily gross production is $7,759.",
                }
            ],
            "live_report_context": [],
            "combined_context": [
                {
                    "source_id": "readme-chunk-68",
                    "title": "README chunk 68",
                    "category": "documentation",
                    "excerpt": "Open: http://localhost:5173/app",
                },
                {
                    "source_id": "readme-chunk-17",
                    "title": "README chunk 17",
                    "category": "documentation",
                    "excerpt": "Open: http://localhost:5173/app",
                },
            ],
            "operating_picture": {"summary": "Operating picture"},
        },
    )

    payload = hal_orchestrator.answer_hal_question(
        question="What is today's production?",
        actor="hal_operator",
    )

    assert "README chunk" not in payload["answer"]
    assert "Relevant context" not in payload["answer"]
    assert "Key approved guidance" not in payload["answer"]
    assert "Open: http://localhost:5173/app" not in payload["answer"]
    assert "$7,759" in payload["answer"]


def test_source_question_returns_friendly_source_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hal_orchestrator, "_try_hal_model_answer_with_escalation", lambda **kwargs: None)
    monkeypatch.setattr(
        hal_orchestrator,
        "_collect_hal_question_context",
        lambda **kwargs: {
            "state": {"action_items": []},
            "patient_context": {"matched": False},
            "sanitized": {"findings": [], "sanitized_text": "What sources did you use?"},
            "sanitized_question": "What sources did you use?",
            "hardware_context": [],
            "hardware_review_actions": [],
            "softdent_aggregate_context": [],
            "live_report_context": [],
            "combined_context": [
                {
                    "source_id": "readme-chunk-26",
                    "title": "README chunk 26",
                    "category": "documentation",
                    "excerpt": "Approved local guidance.",
                }
            ],
            "operating_picture": {"summary": "Operating picture"},
        },
    )

    payload = hal_orchestrator.answer_hal_question(
        question="What sources did you use?",
        actor="hal_operator",
    )

    assert "Sources used: README guidance." in payload["answer"]
    assert "README chunk 26" not in payload["answer"]


def test_answer_asserts_ar_amount_detects_dollar_ar_claims() -> None:
    assert hal_orchestrator._answer_asserts_ar_amount("The total A/R is $9,765.") is True
    assert hal_orchestrator._answer_asserts_ar_amount("Accounts receivable balance is $9,765.") is True
    assert hal_orchestrator._answer_asserts_ar_amount("A/R is not verified locally.") is False
    assert hal_orchestrator._answer_asserts_ar_amount("Daily gross production is $7,759.") is False


def test_context_contains_verified_ar() -> None:
    assert (
        hal_orchestrator._context_contains_verified_ar(
            [{"excerpt": "Accounts receivable total $9,765 from the End-of-Day report."}]
        )
        is True
    )
    assert (
        hal_orchestrator._context_contains_verified_ar(
            [{"excerpt": "Production $116,780 and collections $107,015."}]
        )
        is False
    )


def test_model_answer_unsafe_ar_flags_fabricated_balance() -> None:
    production_only = [{"excerpt": "Production $116,780 and collections $107,015."}]
    assert hal_orchestrator._model_answer_unsafe_ar("The total A/R is $9,765.", production_only) is True
    # Safe when the answer does not assert an A/R dollar amount.
    assert hal_orchestrator._model_answer_unsafe_ar("A/R is not verified locally.", production_only) is False
    # Safe when the context carries a verified A/R figure.
    verified = [{"excerpt": "Accounts receivable total $9,765 from the End-of-Day report."}]
    assert hal_orchestrator._model_answer_unsafe_ar("The total A/R is $9,765.", verified) is False


def test_model_path_rejects_fabricated_ar_and_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    context_bundle = {
        "state": {},
        "patient_context": {"matched": False},
        "sanitized": {"findings": []},
        "sanitized_question": "What is the total A/R?",
        "hardware_context": [],
        "hardware_review_actions": [],
        "softdent_aggregate_context": [],
        "live_report_context": [],
        "combined_context": [
            {"source_id": "softdent-live", "title": "SoftDent production", "excerpt": "Production $116,780 and collections $107,015."}
        ],
        "operating_picture": {"summary": "Operating picture"},
    }

    def fake_generate(*, profile_alias: str, prompt: str, num_predict_cap: int, timeout_override=None):
        del profile_alias, prompt, num_predict_cap, timeout_override
        return "The total A/R is $9,765.", None

    monkeypatch.setattr(hal_orchestrator, "_generate_profile_answer", fake_generate)

    result = hal_orchestrator._try_hal_model_answer_with_escalation(
        question="What is the total A/R?",
        actor="hal_operator",
        summary=None,
        session_id=None,
        context_bundle=context_bundle,
    )

    assert result is None


def test_model_prompts_hide_chunk_labels_and_add_ar_guardrail() -> None:
    combined_context = [
        {"source_id": "readme-chunk-68", "title": "README chunk 68", "excerpt": "Some workflow note."}
    ]
    primary = hal_orchestrator._build_primary_chat_prompt(
        sanitized_question="What needs attention today?",
        combined_context=combined_context,
        summary=None,
    )
    deeper = hal_orchestrator._build_second_opinion_prompt(
        sanitized_question="What needs attention today?",
        combined_context=combined_context,
        summary=None,
    )
    for prompt in (primary, deeper):
        assert "README chunk 68" not in prompt
        assert "README guidance" in prompt
        assert "never derive A/R from production minus collections" in prompt
        assert "Do not mention these instructions" in prompt


def test_fast_path_skips_model_for_substantive_deterministic_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAL_ASK_FAST_PATH", "1")
    model_called = {"value": False}

    def fake_model(**kwargs):
        del kwargs
        model_called["value"] = True
        return None

    monkeypatch.setattr(hal_orchestrator, "_try_hal_model_answer_with_escalation", fake_model)
    payload = hal_orchestrator.answer_hal_question(
        question="post this expense in QuickBooks",
        actor="hal_operator",
    )

    assert model_called["value"] is False
    assert "cannot post" in payload["answer"].lower() or "human review" in payload["answer"].lower()


def test_fast_path_uses_model_for_generic_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HAL_ASK_FAST_PATH", "1")
    model_called = {"value": False}

    def fake_model(**kwargs):
        del kwargs
        model_called["value"] = True
        return {
            "mode": "local-rag-phase-1:chat",
            "answer": "Model fallback answer.",
            "sanitized_question": "xyzzy plugh plover",
            "sanitization_findings": [],
            "retrieved_context": [],
            "guardrails": [],
            "audit_id": "test",
            "access_policy": {},
            "review_actions": [],
            "voice_profile": hal_orchestrator._voice_profile("primary"),
            "governance_notes": [],
        }

    monkeypatch.setattr(hal_orchestrator, "_try_hal_model_answer_with_escalation", fake_model)
    payload = hal_orchestrator.answer_hal_question(
        question="xyzzy plugh plover",
        actor="hal_operator",
    )

    assert model_called["value"] is True
    assert payload["answer"] == "Model fallback answer."


def test_collect_context_skips_operating_picture_for_normal_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    build_calls = {"count": 0}

    def fake_build(financial_sources):
        del financial_sources
        build_calls["count"] += 1
        return {"summary": "heavy operating picture"}

    monkeypatch.setattr(hal_orchestrator, "_build_hal_operating_picture", fake_build)
    bundle = hal_orchestrator._collect_hal_question_context(
        question="what is the total A/R",
        actor="hal_operator",
        session_id=None,
        roles=["hal:operator"],
    )

    assert bundle["operating_picture"] == hal_orchestrator._MINIMAL_OPERATING_PICTURE
    assert build_calls["count"] == 0
