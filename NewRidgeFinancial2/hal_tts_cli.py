"""CLI for HAL neural TTS — run under 64-bit Python (edge-tts + pygame)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time

from hal_tts import neural_tts_available, synthesize_text_sync, tts_status


def _play_mp3_mci(path: str) -> bool:
    """Play MP3 via Windows MCI (winsound cannot decode MP3)."""
    if sys.platform != "win32":
        return False
    import ctypes

    winmm = ctypes.windll.winmm
    alias = f"haltts{os.getpid()}"
    buf = ctypes.create_unicode_buffer(255)
    # Escape backslashes for MCI.
    mci_path = path.replace("\\", "\\\\")
    if winmm.mciSendStringW(f'open "{mci_path}" type mpegvideo alias {alias}', buf, 255, None) != 0:
        return False
    try:
        return winmm.mciSendStringW(f"play {alias} wait", buf, 255, None) == 0
    finally:
        winmm.mciSendStringW(f"close {alias}", None, 0, None)


def _play_mp3(data: bytes) -> None:
    if not data:
        raise RuntimeError("empty audio")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    path = ""
    try:
        fd, path = tempfile.mkstemp(prefix="hal_tts_cli_", suffix=".mp3")
        os.close(fd)
        with open(path, "wb") as handle:
            handle.write(data)
        try:
            import pygame

            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.04)
            return
        except Exception:
            pass
        if _play_mp3_mci(path):
            return
        raise RuntimeError("no audio playback backend (need pygame or Windows MCI for MP3)")
    finally:
        if path:
            try:
                os.remove(path)
            except OSError:
                pass


def cmd_status(_args: argparse.Namespace) -> int:
    print(json.dumps(tts_status()))
    return 0 if neural_tts_available() else 1


def cmd_speak(args: argparse.Namespace) -> int:
    text = str(args.text or "").strip()
    if not text:
        print(json.dumps({"ok": False, "error": "text required"}), file=sys.stderr)
        return 2
    if not neural_tts_available():
        print(json.dumps({"ok": False, "error": "edge-tts not installed"}), file=sys.stderr)
        return 1
    t0 = time.time()
    audio = synthesize_text_sync(text, {"voice": args.voice or "hal"})
    if args.out:
        with open(args.out, "wb") as handle:
            handle.write(audio)
    else:
        _play_mp3(audio)
    print(
        json.dumps(
            {
                "ok": True,
                "engine": "edge-neural",
                "voice": args.voice or "hal",
                "bytes": len(audio),
                "durationSec": round(time.time() - t0, 2),
            }
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HAL neural TTS CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    status_p = sub.add_parser("status", help="Print neural TTS availability JSON")
    status_p.set_defaults(func=cmd_status)

    speak_p = sub.add_parser("speak", help="Synthesize and play text")
    speak_p.add_argument("--text", required=True, help="Text to speak")
    speak_p.add_argument("--voice", default="hal", help="Voice profile (hal, aria, …)")
    speak_p.add_argument("--out", default="", help="Optional mp3 output path (skip playback)")
    speak_p.set_defaults(func=cmd_speak)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
