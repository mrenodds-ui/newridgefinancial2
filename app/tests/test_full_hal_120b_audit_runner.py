import importlib.util
from pathlib import Path
import sys


def load_audit_runner_module():
    module_path = Path(__file__).resolve().parents[2] / "AI_Workspace" / "full_hal_120b_audit_20260621.py"
    spec = importlib.util.spec_from_file_location("full_hal_120b_audit_runner", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_call_model_falls_back_from_chat_completions_to_generate(monkeypatch):
    audit_runner = load_audit_runner_module()
    monkeypatch.setattr(audit_runner, "TRANSPORT", "chat-completions")

    calls: list[str] = []

    def fake_chat(system_prompt, user_prompt, *, max_tokens):
        del system_prompt, user_prompt, max_tokens
        calls.append("chat")
        return (
            {
                "choices": [
                    {
                        "message": {"content": ""},
                        "finish_reason": "length",
                    }
                ]
            },
            "",
            "length",
        )

    def fake_generate(system_prompt, user_prompt, *, max_tokens):
        del system_prompt, user_prompt, max_tokens
        calls.append("generate")
        return (
            {"response": "ISSUE | high | routes | truncated audit | dropped findings | use generate fallback"},
            "ISSUE | high | routes | truncated audit | dropped findings | use generate fallback",
            "stop",
        )

    monkeypatch.setattr(audit_runner, "_call_model_via_chat_completions", fake_chat)
    monkeypatch.setattr(audit_runner, "_call_model_via_generate", fake_generate)

    body, text, finish_reason = audit_runner.call_model("system", "user", max_tokens=128)

    assert calls == ["chat", "generate"]
    assert text == "ISSUE | high | routes | truncated audit | dropped findings | use generate fallback"
    assert finish_reason == "stop"
    assert body["transport_fallback"] == {
        "from": "chat-completions",
        "to": "ollama-generate",
        "reason": "empty_response",
    }
    assert "chat_completions_attempt" in body


def test_call_model_keeps_chat_completion_when_content_is_present(monkeypatch):
    audit_runner = load_audit_runner_module()
    monkeypatch.setattr(audit_runner, "TRANSPORT", "chat-completions")

    def fake_chat(system_prompt, user_prompt, *, max_tokens):
        del system_prompt, user_prompt, max_tokens
        return (
            {
                "choices": [
                    {
                        "message": {"content": "NO_ISSUES | routes_hal_redaction"},
                        "finish_reason": "stop",
                    }
                ]
            },
            "NO_ISSUES | routes_hal_redaction",
            "stop",
        )

    def fail_generate(system_prompt, user_prompt, *, max_tokens):
        del system_prompt, user_prompt, max_tokens
        raise AssertionError("generate fallback should not run when chat content is usable")

    monkeypatch.setattr(audit_runner, "_call_model_via_chat_completions", fake_chat)
    monkeypatch.setattr(audit_runner, "_call_model_via_generate", fail_generate)

    body, text, finish_reason = audit_runner.call_model("system", "user", max_tokens=96)

    assert text == "NO_ISSUES | routes_hal_redaction"
    assert finish_reason == "stop"
    assert "transport_fallback" not in body