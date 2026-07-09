"""HAL neural TTS via Microsoft Edge voices."""

from __future__ import annotations

import asyncio
import html
import json
from typing import Any

VOICE = "en-US-GuyNeural"
VOICE_FALLBACK = "en-US-AriaNeural"
PROFILE = "hal-conversational-v2"
SENTENCE_BREAK_MS = 140

TEST_LINE = "HAL is online and ready."


def neural_tts_available() -> bool:
    try:
        import edge_tts  # noqa: F401

        return True
    except ImportError:
        return False


def tts_status() -> dict[str, Any]:
    return {
        "ok": neural_tts_available(),
        "voice": VOICE,
        "engine": "edge-neural",
        "profile": PROFILE,
    }


def _escape_ssml(text: str) -> str:
    return html.escape(str(text or "").strip(), quote=False)


def resolve_voice_name(payload: dict[str, Any] | None) -> str:
    if not payload:
        return VOICE
    requested = str(payload.get("voice") or "").strip().lower()
    if requested in ("aria", "aria-neural", "jenny", "jenny-neural"):
        return VOICE_FALLBACK
    if requested in ("hal9000", "guy", "guy-neural", "hal", "david"):
        return VOICE
    explicit = str(payload.get("voice") or "").strip()
    if explicit in (VOICE, VOICE_FALLBACK):
        return explicit
    return VOICE


def segments_to_ssml(segments: list[dict[str, Any]], *, voice: str | None = None) -> str:
    voice_name = voice or VOICE
    body: list[str] = []
    for seg in segments:
        if not seg or not seg.get("text"):
            continue
        text = _escape_ssml(str(seg["text"]).strip())
        if not text:
            continue
        body.append(f'<prosody rate="+12%" pitch="+0%" volume="medium">{text}</prosody>')
        body.append(f'<break time="{SENTENCE_BREAK_MS}ms"/>')
    if body and body[-1].startswith("<break"):
        body.pop()
    inner = "".join(body)
    return (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xml:lang="en-US"><voice name="{voice_name}">{inner}</voice></speak>'
    )


async def _stream_ssml(ssml: str) -> bytes:
    import edge_tts

    audio = b""
    for voice in (VOICE, VOICE_FALLBACK):
        try:
            communicate = edge_tts.Communicate(ssml, voice)
            audio = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio += chunk["data"]
            if audio:
                return audio
        except Exception:
            continue
    raise RuntimeError("HAL neural TTS produced no audio")


async def synthesize_segments(
    segments: list[dict[str, Any]],
    *,
    voice: str | None = None,
) -> bytes:
    if not segments:
        raise ValueError("segments required")
    ssml = segments_to_ssml(segments, voice=voice)
    return await _stream_ssml(ssml)


async def synthesize_test() -> bytes:
    return await synthesize_segments([{"text": TEST_LINE}])


def synthesize_segments_sync(segments: list[dict[str, Any]], payload: dict[str, Any] | None = None) -> bytes:
    payload = payload or {}
    voice = resolve_voice_name(payload)
    return asyncio.run(synthesize_segments(segments, voice=voice))


def synthesize_text_sync(text: str, payload: dict[str, Any] | None = None) -> bytes:
    cleaned = str(text or "").strip()
    if not cleaned:
        raise ValueError("text required")
    return synthesize_segments_sync([{"text": cleaned}], payload)


def synthesize_test_sync() -> bytes:
    return asyncio.run(synthesize_test())


def parse_tts_request(body: str | bytes | None) -> dict[str, Any]:
    if not body:
        return {}
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
