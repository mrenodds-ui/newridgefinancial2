import builtins
import types

import app.hal.hardware_tools as hardware_tools


def test_get_monitor_status_fails_closed_when_library_missing(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "monitorcontrol":
            raise ImportError("monitorcontrol package not available")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    status = hardware_tools.get_monitor_status()

    assert status["source_backend"] == "empty"
    assert status["brightness"] is None
    assert status["health"]["connected"] is False
    assert "not available" in status["health"]["error"]


def test_get_monitor_status_handles_empty_monitor_list_gracefully(monkeypatch):
    fake_module = types.SimpleNamespace(get_monitors=lambda: [])
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "monitorcontrol":
            return fake_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    status = hardware_tools.get_monitor_status()

    assert status["source_backend"] == "empty"
    assert status["health"]["connected"] is False
    assert "No physical monitors discovered" in status["health"]["error"]


def test_get_monitor_status_captures_raw_vcp_input_code(monkeypatch):
    class FakeMonitor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def get_luminance(self):
            return 42

        def get_contrast(self):
            return 68

        def get_input_source(self):
            return 17

    fake_module = types.SimpleNamespace(get_monitors=lambda: [FakeMonitor()])
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "monitorcontrol":
            return fake_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    status = hardware_tools.get_monitor_status()

    assert status["source_backend"] == "ddc_ci"
    assert status["input_source"] == "17"
    assert status["raw_vcp_codes"] == {
        "input_source_raw": 17,
        "input_source_raw_type": "int",
    }


def test_build_monitor_mutation_intent_parses_explicit_brightness_request():
    intent = hardware_tools.build_monitor_mutation_intent("Please set brightness to 30% on the monitor.")

    assert intent == {
        "action_type": "SET_LUMINANCE",
        "target_value": 30,
        "human_review_required": True,
        "status": "pending_confirmation",
    }


def test_build_monitor_mutation_intent_rejects_out_of_bounds_request():
    intent = hardware_tools.build_monitor_mutation_intent("Set brightness to 130%.")

    assert intent is None