import pytest

from app.evaluation import audio
from app.evaluation.client import handle_ai_response


def test_get_elevenlabs_api_key_requires_env(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setattr(audio, "PROJECT_DOTENV_PATH", audio.PROJECT_ROOT / ".env.missing")

    with pytest.raises(audio.AudioPlaybackError, match="Missing ELEVENLABS_API_KEY"):
        audio.get_elevenlabs_api_key()


def test_get_elevenlabs_api_key_loads_project_dotenv(monkeypatch, tmp_path):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("ELEVENLABS_API_KEY=dotenv-test-key\n", encoding="utf-8")
    monkeypatch.setattr(audio, "PROJECT_DOTENV_PATH", dotenv_path)

    assert audio.get_elevenlabs_api_key() == "dotenv-test-key"


def test_speak_text_uses_streaming_sdk(monkeypatch):
    calls = {"streamed": False}

    class FakeTextToSpeech:
        def stream(self, *, text, voice_id, model_id):
            assert text == "hello"
            assert voice_id == "voice-123"
            assert model_id == audio.DEFAULT_ELEVENLABS_MODEL_ID
            return [b"chunk"]

    class FakeClient:
        def __init__(self, api_key):
            assert api_key == "test-key"
            self.text_to_speech = FakeTextToSpeech()

    def fake_stream(chunks):
        assert list(chunks) == [b"chunk"]
        calls["streamed"] = True

    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setattr(audio, "_load_elevenlabs_sdk", lambda: (FakeClient, fake_stream, None, audio.AudioPlaybackError))

    assert audio.speak_text("hello", voice_id="voice-123") is True
    assert calls["streamed"] is True


def test_handle_ai_response_can_trigger_async_audio(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        "app.evaluation.client.generate_response",
        lambda **kwargs: "spoken response",
    )

    def fake_speak_text_async(text, *, voice_id=None, model_id=audio.DEFAULT_ELEVENLABS_MODEL_ID, api_key=None):
        captured["text"] = text
        captured["voice_id"] = voice_id
        return object()

    monkeypatch.setattr("app.evaluation.client.speak_text_async", fake_speak_text_async)

    response = handle_ai_response(
        base_url="http://127.0.0.1:11434",
        profile={"model": "mistral-small3.1:24b"},
        prompt="Say hi",
        timeout_seconds=30,
        speak=True,
        async_playback=True,
        voice_id="voice-abc",
    )

    assert response == "spoken response"
    assert captured == {"text": "spoken response", "voice_id": "voice-abc"}