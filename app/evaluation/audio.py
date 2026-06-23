from __future__ import annotations

import os
from pathlib import Path
from threading import Thread
from typing import Any

from dotenv import load_dotenv

DEFAULT_ELEVENLABS_MODEL_ID = "eleven_multilingual_v2"
DEFAULT_ELEVENLABS_VOICE_ID = "pNInz6obpgDQGcFmaJgB"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_DOTENV_PATH = PROJECT_ROOT / ".env"


class AudioPlaybackError(RuntimeError):
    pass


def load_project_dotenv() -> None:
    if PROJECT_DOTENV_PATH.exists():
        load_dotenv(PROJECT_DOTENV_PATH, override=False)


def _load_elevenlabs_sdk() -> tuple[Any, Any, Any, Any]:
    try:
        from elevenlabs import stream
        from elevenlabs.client import ElevenLabs
        try:
            from elevenlabs.play import play
        except ImportError:
            play = None
    except ImportError as exc:
        raise AudioPlaybackError(
            "ElevenLabs SDK is not installed. Install 'elevenlabs' in the active environment."
        ) from exc
    return ElevenLabs, stream, play, AudioPlaybackError


def get_elevenlabs_api_key(explicit_api_key: str | None = None) -> str:
    load_project_dotenv()
    api_key = explicit_api_key or os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise AudioPlaybackError("Missing ELEVENLABS_API_KEY in environment variables or project .env file.")
    return api_key


def build_elevenlabs_client(api_key: str | None = None) -> Any:
    resolved_api_key = get_elevenlabs_api_key(api_key)
    eleven_labs_client, _, _, _ = _load_elevenlabs_sdk()
    return eleven_labs_client(api_key=resolved_api_key)


def speak_text(
    text: str,
    *,
    voice_id: str | None = None,
    model_id: str = DEFAULT_ELEVENLABS_MODEL_ID,
    api_key: str | None = None,
) -> bool:
    if not text or not text.strip():
        raise ValueError("Text-to-speech requires non-empty text.")

    client = build_elevenlabs_client(api_key)
    _, stream_audio, play_audio, _ = _load_elevenlabs_sdk()
    resolved_voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID") or DEFAULT_ELEVENLABS_VOICE_ID

    try:
        audio_stream = client.text_to_speech.stream(
            text=text,
            voice_id=resolved_voice_id,
            model_id=model_id,
        )
        stream_audio(audio_stream)
        return True
    except Exception as stream_exc:
        if play_audio is None:
            raise AudioPlaybackError(f"Audio playback failed: {stream_exc}") from stream_exc

        try:
            audio = client.text_to_speech.convert(
                text=text,
                voice_id=resolved_voice_id,
                model_id=model_id,
                output_format="mp3_44100_128",
            )
            play_audio(audio)
            return True
        except Exception as convert_exc:
            raise AudioPlaybackError(f"Audio playback failed: {convert_exc}") from convert_exc


def speak_text_async(
    text: str,
    *,
    voice_id: str | None = None,
    model_id: str = DEFAULT_ELEVENLABS_MODEL_ID,
    api_key: str | None = None,
) -> Thread:
    worker = Thread(
        target=speak_text,
        kwargs={
            "text": text,
            "voice_id": voice_id,
            "model_id": model_id,
            "api_key": api_key,
        },
        daemon=True,
        name="elevenlabs-audio-playback",
    )
    worker.start()
    return worker