"""Miranda Priestly neural TTS — Streep-informed SSML via Microsoft Edge voices."""

from __future__ import annotations

import asyncio
import html
import json
import re
from pathlib import Path
from typing import Any

VOICE = "en-US-AriaNeural"
VOICE_FALLBACK = "en-US-JennyNeural"
PROFILE = "miranda-glacial-v1"

CALIBRATION_PATH = (
    Path(__file__).resolve().parent / "data" / "miranda_reference" / "miranda_tts_calibration.json"
)

# Film Miranda: glacial pace — Streep near-whisper, long beats between clauses (Devil Wears Prada).
SENTENCE_BREAK_MS = 1100
BRIDGE_DEFAULT_MS = 1050

KIND_PROSODY: dict[str, tuple[str, str, str]] = {
    "setup": ("-44%", "-6%", "x-soft"),
    "leanIn": ("-50%", "-5%", "soft"),
    "stress": ("-68%", "-8%", "soft"),
    "cutting": ("-54%", "+1%", "soft"),
    "train": ("-40%", "-4%", "soft"),
    "dismissal": ("-74%", "-12%", "x-soft"),
}

DEMO_BEATS: list[dict[str, Any]] = [
    {"text": "Please", "kind": "setup", "bridgeMs": 780},
    {"text": "bore someone else with your questions.", "kind": "stress", "pauseAfter": 2600},
    {"text": "I couldn't have been", "kind": "setup", "bridgeMs": 1100},
    {"text": "clearer.", "kind": "stress", "pauseAfter": 2800},
    {"text": "By all means, move at a", "kind": "setup", "bridgeMs": 980},
    {"text": "glacial pace.", "kind": "stress", "pauseAfter": 1800},
    {"text": "You know how that thrills me.", "kind": "cutting", "pauseAfter": 2800},
    {"text": "Florals?", "kind": "setup", "bridgeMs": 1200},
    {"text": "For spring?", "kind": "cutting", "bridgeMs": 1050},
    {"text": "Groundbreaking.", "kind": "stress", "pauseAfter": 3200},
    {"text": "That's", "kind": "setup", "bridgeMs": 1300},
    {"text": "all.", "kind": "dismissal", "pauseBeforeMs": 1900},
]

_calibration_cache: dict[str, Any] | None = None


def _apply_calibration(data: dict[str, Any]) -> None:
    global SENTENCE_BREAK_MS, BRIDGE_DEFAULT_MS, KIND_PROSODY, DEMO_BEATS, PROFILE

    PROFILE = str(data.get("profile") or PROFILE)
    timing = data.get("timing") if isinstance(data.get("timing"), dict) else {}
    SENTENCE_BREAK_MS = int(timing.get("sentence_break_ms") or SENTENCE_BREAK_MS)
    BRIDGE_DEFAULT_MS = int(timing.get("bridge_default_ms") or BRIDGE_DEFAULT_MS)

    neural = data.get("neural_prosody")
    if isinstance(neural, dict):
        for kind, vals in neural.items():
            if not isinstance(vals, dict):
                continue
            rate = str(vals.get("rate") or KIND_PROSODY.get(kind, KIND_PROSODY["leanIn"])[0])
            pitch = str(vals.get("pitch") or KIND_PROSODY.get(kind, KIND_PROSODY["leanIn"])[1])
            volume = str(vals.get("volume") or KIND_PROSODY.get(kind, KIND_PROSODY["leanIn"])[2])
            KIND_PROSODY[kind] = (rate, pitch, volume)

    stress_pause = int(timing.get("pause_after_stress_ms") or 2800)
    dismissal_pause = int(timing.get("pause_after_dismissal_ms") or 3000)
    bridge = int(timing.get("bridge_default_ms") or BRIDGE_DEFAULT_MS)
    dismissal_before = int(timing.get("dismissal_pause_ms") or 1900)

    DEMO_BEATS = [
        {"text": "Please", "kind": "setup", "bridgeMs": bridge},
        {"text": "bore someone else with your questions.", "kind": "stress", "pauseAfter": stress_pause},
        {"text": "I couldn't have been", "kind": "setup", "bridgeMs": bridge},
        {"text": "clearer.", "kind": "stress", "pauseAfter": stress_pause},
        {"text": "By all means, move at a", "kind": "setup", "bridgeMs": bridge},
        {"text": "glacial pace.", "kind": "stress", "pauseAfter": int(stress_pause * 0.72)},
        {"text": "You know how that thrills me.", "kind": "cutting", "pauseAfter": stress_pause},
        {"text": "Florals?", "kind": "setup", "bridgeMs": int(bridge * 1.08)},
        {"text": "For spring?", "kind": "cutting", "bridgeMs": bridge},
        {"text": "Groundbreaking.", "kind": "stress", "pauseAfter": int(stress_pause * 1.12)},
        {"text": "That's", "kind": "setup", "bridgeMs": int(bridge * 1.15)},
        {"text": "all.", "kind": "dismissal", "pauseBeforeMs": dismissal_before},
    ]


def load_calibration(force: bool = False) -> dict[str, Any]:
    global _calibration_cache
    if _calibration_cache is not None and not force:
        return _calibration_cache

    data: dict[str, Any] = {}
    if CALIBRATION_PATH.is_file():
        try:
            loaded = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
                _apply_calibration(data)
        except (OSError, json.JSONDecodeError):
            pass

    _calibration_cache = data
    return data


def tts_status() -> dict[str, Any]:
    cal = load_calibration()
    return {
        "ok": neural_tts_available(),
        "voice": VOICE,
        "engine": "edge-neural",
        "profile": PROFILE,
        "calibration": {
            "profile": cal.get("profile"),
            "metrics": cal.get("metrics"),
            "timing": cal.get("timing"),
            "browser_delivery": cal.get("browser_delivery"),
        },
    }


def neural_tts_available() -> bool:
    try:
        import edge_tts  # noqa: F401

        return True
    except ImportError:
        return False


def _escape_ssml(text: str) -> str:
    return html.escape(str(text or "").strip(), quote=False)


def beat_to_ssml(beat: dict[str, Any], prev_kind: str | None = None) -> str:
    kind = str(beat.get("kind") or "leanIn")
    rate, pitch, volume = KIND_PROSODY.get(kind, KIND_PROSODY["leanIn"])
    text = _escape_ssml(beat.get("text") or "")
    if not text:
        return ""

    parts: list[str] = []
    pause_before = int(beat.get("pauseBeforeMs") or 0)
    if pause_before > 0:
        parts.append(f'<break time="{pause_before}ms"/>')
    elif kind == "stress" and prev_kind == "setup":
        bridge = int(beat.get("bridgeMs") or BRIDGE_DEFAULT_MS)
        parts.append(f'<break time="{bridge}ms"/>')

    parts.append(f'<prosody rate="{rate}" pitch="{pitch}" volume="{volume}">{text}</prosody>')

    pause_after = int(beat.get("pauseAfter") or 0)
    if pause_after > 0:
        parts.append(f'<break time="{pause_after}ms"/>')

    return "".join(parts)


def _split_sentences(text: str) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []
    parts = re.split(r"(?<=[.!?])\s+", raw)
    return [p.strip() for p in parts if p.strip()]


def expand_glacial_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One sentence per beat — Miranda never rushes a paragraph (film delivery)."""
    out: list[dict[str, Any]] = []
    for seg in segments:
        if not seg or not seg.get("text"):
            continue
        text = str(seg["text"]).strip()
        kind = str(seg.get("kind") or ("dismissal" if seg.get("dismissive") else "leanIn"))
        dismissive = bool(seg.get("dismissive"))
        parts = _split_sentences(text) if len(text) > 65 else [text]
        for idx, part in enumerate(parts):
            piece = part.strip()
            if not piece:
                continue
            beat: dict[str, Any] = {
                "text": piece,
                "kind": "dismissal" if dismissive and idx == len(parts) - 1 else kind,
                "dismissive": dismissive and idx == len(parts) - 1,
            }
            if idx == 0 and seg.get("pauseBeforeMs"):
                beat["pauseBeforeMs"] = int(seg["pauseBeforeMs"])
            elif idx > 0:
                beat["pauseBeforeMs"] = SENTENCE_BREAK_MS
            out.append(beat)
    return out


def segments_to_ssml(segments: list[dict[str, Any]]) -> str:
    segments = expand_glacial_segments(segments)
    body: list[str] = []
    prev_kind: str | None = None
    for seg in segments:
        if not seg or not seg.get("text"):
            continue
        piece = beat_to_ssml(
            {
                "text": seg.get("text"),
                "kind": seg.get("kind") or ("dismissal" if seg.get("dismissive") else "leanIn"),
                "pauseBeforeMs": seg.get("pauseBeforeMs"),
                "bridgeMs": seg.get("bridgeMs"),
            },
            prev_kind=prev_kind,
        )
        if piece:
            body.append(piece)
            prev_kind = str(seg.get("kind") or "leanIn")
    inner = "".join(body)
    return (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xml:lang="en-US"><voice name="{VOICE}">{inner}</voice></speak>'
    )


def demo_to_ssml() -> str:
    return segments_to_ssml(DEMO_BEATS)


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
    raise RuntimeError("Miranda neural TTS produced no audio")


async def synthesize_segments(segments: list[dict[str, Any]]) -> bytes:
    if not segments:
        raise ValueError("segments required")
    ssml = segments_to_ssml(segments)
    return await _stream_ssml(ssml)


async def synthesize_demo() -> bytes:
    return await _stream_ssml(demo_to_ssml())


async def synthesize_text(text: str) -> bytes:
    cleaned = str(text or "").strip()
    if not cleaned:
        raise ValueError("text required")
    segments = [{"text": cleaned, "kind": "leanIn"}]
    return await synthesize_segments(segments)


def synthesize_segments_sync(segments: list[dict[str, Any]]) -> bytes:
    return asyncio.run(synthesize_segments(segments))


def synthesize_demo_sync() -> bytes:
    return asyncio.run(synthesize_demo())


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


load_calibration()
