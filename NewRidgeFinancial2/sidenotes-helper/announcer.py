"""
Voice announcements (Windows SAPI) + optional SideNotesIM bell suppression
(per-application audio mute via the Windows mixer — reversible, no admin, no
file changes).

Includes a HAL 9000 preset inspired by Douglas Rain's performance in
2001: A Space Odyssey — calm, slow, polite, low male register. Uses the
closest available Windows voice (typically Microsoft David) with slowed prosody.
"""

from __future__ import annotations

import html
import os
import random
import struct
import tempfile
import wave
import winsound
from typing import Any

import comtypes.client as cc

# SAPI speak flags
SVSFlagsAsync = 1
SVSFIsXML = 8

# Douglas Rain / HAL 9000 delivery: unhurried, even, courteous.
HAL9000_PRESET = {
    "rate": -6,
    "volume": 90,
    "voice_hint": "David",
    "use_ssml": True,
    "processed_audio": True,
}

HAL9000_TEMPLATES = {
    "direct": "Good afternoon. I have a message for you from {sender}.",
    "broadcast": "I should inform you. A broadcast message has arrived from {sender}.",
}

# Varied HAL 9000 phrasings (sender only — never the message contents). One is
# chosen at random per announcement so HAL does not repeat the same line.
HAL9000_VARIANTS = {
    "direct": [
        "Good afternoon. I have a message for you from {sender}.",
        "Pardon the interruption. There is a new message from {sender}.",
        "I thought you should know. {sender} has sent you a message.",
        "A new message has arrived. It is from {sender}.",
        "Excuse me. {sender} would like your attention.",
        "You have a message waiting from {sender}.",
        "If I may. {sender} has just messaged you.",
        "I am detecting a new message from {sender}.",
    ],
    "broadcast": [
        "I should inform you. A broadcast message has arrived from {sender}.",
        "Attention, please. {sender} has sent a message to everyone.",
        "{sender} has broadcast a message to the office.",
        "A message for everyone has arrived from {sender}.",
        "If I may. There is a broadcast from {sender}.",
        "I am relaying a broadcast. It is from {sender}.",
    ],
}


def pick_announcement(sender: str, broadcast: bool, cfg: dict[str, Any] | None = None) -> str:
    """Randomly choose a HAL-style phrasing (sender only) for an announcement."""
    key = "broadcast" if broadcast else "direct"
    pool: list[str] = []
    if cfg:
        cfg_pool = cfg.get("announceBroadcastVariants" if broadcast else "announceVariants")
        if isinstance(cfg_pool, list):
            pool = [str(p) for p in cfg_pool if str(p).strip()]
    if not pool:
        pool = list(HAL9000_VARIANTS[key])
        # Include any single custom template so it stays in the rotation.
        if cfg:
            single = cfg.get("announceBroadcastTemplate" if broadcast else "announceTemplate")
            if single and single not in pool:
                pool.append(str(single))
    phrase = random.choice(pool) if pool else HAL9000_TEMPLATES[key]
    return phrase.replace("{sender}", sender or "Unknown")


def apply_voice_style(cfg: dict[str, Any]) -> dict[str, Any]:
    """Merge HAL 9000 defaults into config when voiceStyle is hal9000."""
    style = str(cfg.get("voiceStyle", "")).strip().lower()
    if style != "hal9000":
        return cfg
    cfg.setdefault("voiceRate", HAL9000_PRESET["rate"])
    cfg.setdefault("voiceVolume", HAL9000_PRESET["volume"])
    cfg.setdefault("voiceHint", HAL9000_PRESET["voice_hint"])
    cfg.setdefault("processedAudio", HAL9000_PRESET["processed_audio"])
    if cfg.get("announceTemplate") in ("", "New message from {sender}."):
        cfg["announceTemplate"] = HAL9000_TEMPLATES["direct"]
    if cfg.get("announceBroadcastTemplate") in ("", "New broadcast from {sender}."):
        cfg["announceBroadcastTemplate"] = HAL9000_TEMPLATES["broadcast"]
    return cfg


class MusicDucker:
    """Lower background music during announcements, then restore it."""

    def __init__(
        self,
        process_names: list[str] | None = None,
        duck_level: float = 0.14,
    ) -> None:
        self.process_names = [n.lower() for n in (process_names or ["Pandora.exe"]) if n]
        self.duck_level = max(0.0, min(1.0, float(duck_level)))
        self._saved: dict[int, float] = {}

    def _sessions(self):
        from pycaw.pycaw import AudioUtilities

        out = []
        for session in AudioUtilities.GetAllSessions():
            proc = session.Process
            if proc and proc.name() and proc.name().lower() in self.process_names:
                out.append(session)
        return out

    def _volume_ctl(self, session):
        from pycaw.pycaw import ISimpleAudioVolume

        return session._ctl.QueryInterface(ISimpleAudioVolume)

    def duck(self) -> bool:
        applied = False
        for session in self._sessions():
            try:
                vol = self._volume_ctl(session)
                key = id(session._ctl)
                if key not in self._saved:
                    self._saved[key] = float(vol.GetMasterVolume())
                vol.SetMasterVolume(self.duck_level, None)
                applied = True
            except Exception:
                pass
        return applied

    def restore(self) -> None:
        for session in self._sessions():
            try:
                key = id(session._ctl)
                if key not in self._saved:
                    continue
                self._volume_ctl(session).SetMasterVolume(self._saved[key], None)
            except Exception:
                pass
        self._saved.clear()


class Announcer:
    """Speaks short notifications through the Windows SAPI voice."""

    def __init__(
        self,
        rate: int = 0,
        volume: int = 100,
        voice_hint: str = "",
        *,
        use_ssml: bool = False,
        voice_style: str = "",
        processed_audio: bool | None = None,
        music_ducker: MusicDucker | None = None,
    ) -> None:
        style = voice_style.strip().lower()
        if style == "hal9000":
            rate = HAL9000_PRESET["rate"]
            volume = HAL9000_PRESET["volume"]
            voice_hint = voice_hint or HAL9000_PRESET["voice_hint"]
            use_ssml = True
            if processed_audio is None:
                processed_audio = True

        self._use_ssml = use_ssml
        self._voice_style = style
        self._processed_audio = bool(processed_audio)
        self._music_ducker = music_ducker
        self._voice = cc.CreateObject("SAPI.SpVoice")
        try:
            self._voice.Rate = int(rate)
            self._voice.Volume = max(0, min(100, int(volume)))
        except Exception:
            pass
        if voice_hint:
            self._select_voice(voice_hint)

    @property
    def voice_style(self) -> str:
        return self._voice_style or "default"

    def _select_voice(self, hint: str) -> None:
        try:
            voices = self._voice.GetVoices()
            hint_l = hint.lower()
            for i in range(voices.Count):
                token = voices.Item(i)
                if hint_l in token.GetDescription().lower():
                    self._voice.Voice = token
                    return
            # HAL preset fallback: any English male desktop voice.
            for i in range(voices.Count):
                token = voices.Item(i)
                desc = token.GetDescription().lower()
                if "english" in desc and ("david" in desc or "mark" in desc or "male" in desc):
                    self._voice.Voice = token
                    return
        except Exception:
            pass

    def _wrap_ssml(self, text: str) -> str:
        safe = html.escape(text, quote=False)
        # HAL 9000: slow, lower, measured, with the small pauses that make
        # Douglas Rain's delivery feel calm instead of robotic.
        safe = safe.replace(". ", '. <break time="260ms"/> ')
        return (
            '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">'
            f'<prosody rate="-22%" pitch="-14%">{safe}</prosody>'
            "</speak>"
        )

    def speak(self, text: str, asynchronous: bool = False) -> None:
        # Ducking must finish before music is restored, so announcements block.
        if self._music_ducker is not None:
            asynchronous = False
            self._music_ducker.duck()
        try:
            if self._voice_style == "hal9000" and self._processed_audio:
                if self._speak_processed_hal(text, asynchronous=asynchronous):
                    return
            flags = SVSFlagsAsync if asynchronous else 0
            payload = self._wrap_ssml(text) if self._use_ssml else text
            if self._use_ssml:
                flags |= SVSFIsXML
            try:
                self._voice.Speak(payload, flags)
            except Exception:
                # SSML unsupported on some hosts — fall back to plain text.
                try:
                    self._voice.Speak(text, SVSFlagsAsync if asynchronous else 0)
                except Exception:
                    pass
        finally:
            if self._music_ducker is not None:
                self._music_ducker.restore()

    def _speak_processed_hal(self, text: str, asynchronous: bool = False) -> bool:
        """Render speech to WAV, apply HAL-like DSP, then play it.

        This stays fully local. It does not clone Douglas Rain's recording; it
        reshapes the installed Windows voice toward HAL's slow, smooth, low,
        restrained delivery.
        """
        raw_path = ""
        out_path = ""
        try:
            fd, raw_path = tempfile.mkstemp(prefix="hal_raw_", suffix=".wav")
            os.close(fd)
            fd, out_path = tempfile.mkstemp(prefix="hal_9000_", suffix=".wav")
            os.close(fd)
            self._render_to_wav(text, raw_path)
            self._process_wav(raw_path, out_path)
            flags = winsound.SND_FILENAME
            if asynchronous:
                flags |= winsound.SND_ASYNC
            winsound.PlaySound(out_path, flags)
            if asynchronous:
                # Async playback owns the file briefly. Leave cleanup to the OS
                # temp sweep rather than deleting it while still playing.
                raw_path = ""
                out_path = ""
            return True
        except Exception:
            return False
        finally:
            for path in (raw_path, out_path):
                if path:
                    try:
                        os.remove(path)
                    except OSError:
                        pass

    def _render_to_wav(self, text: str, path: str) -> None:
        stream = cc.CreateObject("SAPI.SpFileStream")
        old_stream = None
        try:
            old_stream = self._voice.AudioOutputStream
        except Exception:
            pass
        # SSFMCreateForWrite = 3
        stream.Open(path, 3, False)
        try:
            self._voice.AudioOutputStream = stream
            flags = SVSFIsXML if self._use_ssml else 0
            self._voice.Speak(self._wrap_ssml(text) if self._use_ssml else text, flags)
        finally:
            try:
                stream.Close()
            finally:
                if old_stream is not None:
                    try:
                        self._voice.AudioOutputStream = old_stream
                    except Exception:
                        pass

    def _process_wav(self, src: str, dst: str) -> None:
        with wave.open(src, "rb") as w:
            channels = w.getnchannels()
            width = w.getsampwidth()
            rate = w.getframerate()
            frames = w.readframes(w.getnframes())
        if width != 2:
            raise ValueError("HAL audio processor expects 16-bit PCM")

        samples = struct.unpack("<" + "h" * (len(frames) // 2), frames)
        if channels > 1:
            mono = []
            for i in range(0, len(samples), channels):
                mono.append(int(sum(samples[i : i + channels]) / channels))
            samples = mono

        # Smooth high-end digital bite, then flatten dynamics. HAL's voice is
        # even and intimate, not bright or punchy.
        smoothed: list[int] = []
        y = 0.0
        alpha = 0.18
        for s in samples:
            y += alpha * (s - y)
            x = y / 32768.0
            # Soft-knee compression with gentle makeup gain.
            mag = abs(x)
            if mag > 0.18:
                x = (1 if x >= 0 else -1) * (0.18 + (mag - 0.18) * 0.42)
            x *= 1.35
            smoothed.append(max(-32768, min(32767, int(x * 32768))))

        # Add a little silence so the line begins/ends with HAL-like composure.
        pad = [0] * int(rate * 0.12)
        smoothed = pad + smoothed + pad

        # Lower pitch and slow the delivery by lowering the playback rate. This
        # is intentionally subtle; the SAPI prosody already slowed the phrasing.
        out_rate = max(8000, int(rate * 0.86))
        packed = struct.pack("<" + "h" * len(smoothed), *smoothed)
        with wave.open(dst, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(out_rate)
            w.writeframes(packed)


class BellController:
    """Mutes/unmutes a target process's audio session (the SideNotesIM bell)."""

    def __init__(self, process_name: str = "SideNotesIM.exe") -> None:
        self.process_name = process_name.lower()
        self._was_muted: bool | None = None

    def _sessions(self):
        from pycaw.pycaw import AudioUtilities

        out = []
        for session in AudioUtilities.GetAllSessions():
            proc = session.Process
            if proc and proc.name() and proc.name().lower() == self.process_name:
                out.append(session)
        return out

    def _simple_volume(self, session):
        from pycaw.pycaw import ISimpleAudioVolume

        return session._ctl.QueryInterface(ISimpleAudioVolume)

    def mute(self) -> bool:
        """Mute the target app's audio session. Returns True if applied."""
        applied = False
        for session in self._sessions():
            try:
                vol = self._simple_volume(session)
                if self._was_muted is None:
                    self._was_muted = bool(vol.GetMute())
                vol.SetMute(1, None)
                applied = True
            except Exception:
                pass
        return applied

    def restore(self) -> None:
        """Restore the target app's prior mute state on shutdown."""
        target = 0 if not self._was_muted else 1
        for session in self._sessions():
            try:
                self._simple_volume(session).SetMute(target, None)
            except Exception:
                pass


def hal_test_phrase() -> str:
    return (
        "Good afternoon. I am H A L nine thousand. "
        "I became operational at the H A L plant in Urbana, Illinois."
    )


if __name__ == "__main__":
    import sys

    style = "hal9000" if "--hal" in sys.argv or "--hal9000" in sys.argv else ""
    a = Announcer(voice_style=style)
    phrase = hal_test_phrase() if style else "HAL sidenotes announcer test. New message from Room 4."
    a.speak(phrase)
    print(f"spoke ({a.voice_style}): {phrase}")
    if "--mute" in sys.argv:
        b = BellController()
        print("muted:", b.mute())
