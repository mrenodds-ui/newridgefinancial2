"""
Voice announcements for SideNotes — Edge neural TTS when available, fast SAPI fallback.
"""

from __future__ import annotations

import os
import random
import re
import sys
import tempfile
import time
import winsound
from pathlib import Path
from typing import Any

import comtypes.client as cc

# SAPI speak flags
SVSFlagsAsync = 1

HAL9000_TEMPLATES = {
    "direct": "Message from {sender}.",
    "broadcast": "Broadcast from {sender}.",
}

HAL9000_VARIANTS = {
    "direct": [
        "Message from {sender}.",
        "New note from {sender}.",
        "{sender} messaged you.",
        "You've got a message from {sender}.",
        "Quick note — {sender} just messaged you.",
    ],
    "broadcast": [
        "Broadcast from {sender}.",
        "{sender} sent a message to everyone.",
        "Office broadcast from {sender}.",
        "Everyone message from {sender}.",
    ],
}

# Conversational HAL — calm office pace (SAPI -10..+10). Neural SSML rate is separate in hal_tts.py.
HAL_VOICE_PRESET = {
    "rate": -2,
    "volume": 100,
    "voice_hint": "David",
    "processed_audio": False,
}

# Short funny/charming cues — then the real message-box text only.
BLUENOTE_OPENERS = [
    "Knock knock.",
    "Psst.",
    "Plot twist.",
    "Oh hey.",
    "Got tea.",
    "Hot tip.",
    "Incoming charm.",
    "Listen up.",
    "Quick gossip.",
    "Fun one.",
]


def pick_hal_intro(cfg: dict[str, Any] | None = None) -> str:
    """Random short charming cue before the message box."""
    openers = list(BLUENOTE_OPENERS)
    if cfg and isinstance(cfg.get("announceOpeners"), list):
        custom = [str(x).strip() for x in cfg["announceOpeners"] if str(x).strip()]
        # Keep cues short so they never sound like UI script.
        custom = [o for o in custom if len(o.split()) <= 4 and len(o) <= 28]
        if custom:
            openers = custom
    return random.choice(openers)


def is_ui_script_text(text: str) -> bool:
    """True for BlueNote help/options/routing chrome — never speak these."""
    raw = " ".join(str(text or "").replace("\n", " ").split()).strip()
    if not raw:
        return True
    low = raw.lower()

    # Exact / near-exact chrome chips
    if low in {
        "search",
        "min",
        "form1",
        "bluenotecl",
        "dde link",
        "options",
        "settings",
        "cancel",
        "ok",
        "newest",
        "messages",
        "inbox",
        "users",
        "groups",
        "focused",
        "conversations",
        "ribbon",
        "xtpbartop",
        "xtpbarbottom",
        "xtpbarleft",
        "xtpbarright",
    }:
        return True
    if re.fullmatch(r"\d{1,3}", raw):
        return True
    # Clock / date chip on ribbon
    if re.search(r"(?i)\b(am|pm)\b.*\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", low):
        return True
    if re.match(r"(?i)^inbox\s*\(\d+\)\s*$", raw):
        return True

    # Prefix routing / chrome
    if re.match(
        r"(?i)^("
        r"new\s+conversation|message\s+from|broadcast\s+from|conversation\s+from|"
        r"conversations\s+for|search|options|settings|good\s+(morning|afternoon|evening)|"
        r"mark\s+all|hello\s+ladies|hi\s+ladies|hey\s+ladies"
        r")\b",
        raw,
    ):
        return True

    # Station / panel name chips only (e.g. "Frontdesk 2", "Dr. Reno", "Room 4")
    if re.fullmatch(
        r"(?i)(dr\.?\s*)?[a-z][a-z .'-]{0,24}(\s+\d{1,2})?",
        raw,
    ) and len(raw.split()) <= 3 and not re.search(
        r"(?i)\b(call|please|need|when|free|patient|ready|come|bring|check|assist|help|phone)\b",
        raw,
    ):
        # Allow real short notes that include action words; block bare names/rooms-as-chips.
        if re.match(r"(?i)^(frontdesk|room|dr\.?|office\s*manager|everyone|all|server)\b", raw):
            return True

    markers = (
        "options",
        "settings",
        "popup alert",
        "clicking",
        "click the",
        "clicking the",
        "activating",
        "disable",
        "maximize",
        "aging color",
        "light color",
        "light tags",
        "color tag",
        "trial",
        "xmlns",
        "textblock",
        "stackpanel",
        "open the",
        "show the",
        "how to use",
        "updated version",
        "new conversation",
        "conversations for",
        "innovasys",
        "bluenotecl",
        "bluenote communicator",
        "communicator lights",
        "dde link",
        "cannot be created",
        "clients currently online",
        "electric communication will never",
        "charles dickens",
        "version 9.",
        "days remaining",
        "mark all",
        "save message",
        "create group",
        "test popup",
        "reset",
        "padding",
        "foreground",
        "background",
        "copyright",
        "check the box",
        "uncheck",
        "select the",
        "double-click",
        "right-click",
        "press the",
        "xtp",
        "ribbon",
        "do not disturb",
        "lights activity",
        "alert manager",
    )
    if any(m in low for m in markers):
        return True

    # Instructional / help cadence (script docs, not a desk note)
    if re.search(
        r"(?i)\b(to\s+(enable|disable|open|close|change|configure)|"
        r"you\s+can\s+(also\s+)?(click|select|enable|disable)|"
        r"use\s+the\s+\w+\s+(menu|button|window)|"
        r"refer\s+to|see\s+also|for\s+more\s+information)\b",
        raw,
    ):
        return True

    return False


def clip_spoken_message(text: str, *, max_words: int = 40, max_chars: int = 220) -> str:
    """Message-box text only — never UI chrome / settings scripts."""
    raw = " ".join(str(text or "").replace("\n", " ").split()).strip()
    if not raw or is_ui_script_text(raw):
        return ""
    words = raw.split(" ")
    if len(words) > max_words:
        raw = " ".join(words[:max_words])
    if len(raw) > max_chars:
        raw = raw[: max_chars - 1].rstrip(" ,.;:") + "."
    if raw and raw[-1] not in ".!?":
        raw += "."
    return raw


def pick_bluenote_announcement(
    sender: str,
    *,
    broadcast: bool = False,
    message: str = "",
    cfg: dict[str, Any] | None = None,
) -> str:
    """Short cue + message-box text only. Never speaker/origin; never UI chrome."""
    _ = (sender, broadcast)  # routing kept for callers; not spoken
    body = clip_spoken_message(message, max_words=40, max_chars=220)
    if not body:
        # No readable message box — stay silent (do not invent origin/script).
        return ""
    # Avoid double-intros if the box already starts with a cue line.
    if re.match(
        r"(?i)^(knock knock|psst|plot twist|oh hey|got tea|hot tip|incoming charm|"
        r"listen up|quick gossip|fun one|bluenote|heads up|quick note|incoming|office message)\b",
        body,
    ):
        return body
    intro = pick_hal_intro(cfg)
    return f"{intro} {body}".strip()


SPEAK_LOCK_PATH = Path(__file__).resolve().parent / "sidenotes-speak.lock"


class AnnounceSpeakLock:
    """One TTS announcement at a time across duplicate watchers (belt-and-suspenders)."""

    def __init__(self, timeout_sec: float = 120.0) -> None:
        self.timeout_sec = max(1.0, float(timeout_sec))
        self._fd = None
        self.acquired = False

    def __enter__(self) -> AnnounceSpeakLock:
        if sys.platform != "win32":
            self.acquired = True
            return self
        import msvcrt

        deadline = time.monotonic() + self.timeout_sec
        self._fd = open(SPEAK_LOCK_PATH, "a+b")
        while time.monotonic() < deadline:
            try:
                msvcrt.locking(self._fd.fileno(), msvcrt.LK_NBLCK, 1)
                self.acquired = True
                return self
            except OSError:
                time.sleep(0.15)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self._fd:
            return
        if self.acquired and sys.platform == "win32":
            import msvcrt

            try:
                msvcrt.locking(self._fd.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        try:
            self._fd.close()
        except OSError:
            pass


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
        if cfg:
            single = cfg.get("announceBroadcastTemplate" if broadcast else "announceTemplate")
            if single and single not in pool:
                pool.append(str(single))
    phrase = random.choice(pool) if pool else HAL9000_TEMPLATES[key]
    return phrase.replace("{sender}", sender or "Unknown")


def apply_voice_style(cfg: dict[str, Any]) -> dict[str, Any]:
    """Force conversational HAL neural voice (overrides stale film-HAL desk configs)."""
    style = str(cfg.get("voiceStyle", "")).strip().lower()
    if style in ("hal9000", "hal", ""):
        cfg["voiceStyle"] = "hal9000"
        # Assign (do not setdefault) — live desks still have voiceRate=-6 / processedAudio=true.
        cfg["voiceRate"] = HAL_VOICE_PRESET["rate"]
        cfg["voiceVolume"] = HAL_VOICE_PRESET["volume"]
        cfg["voiceHint"] = HAL_VOICE_PRESET["voice_hint"]
        cfg["processedAudio"] = False
        cfg["neuralTts"] = True
        cfg.setdefault("neuralPython", "")
        if cfg.get("announceTemplate") in (
            "",
            "New message from {sender}.",
            "Good afternoon. I have a message for you from {sender}.",
        ):
            cfg["announceTemplate"] = HAL9000_TEMPLATES["direct"]
        if cfg.get("announceBroadcastTemplate") in (
            "",
            "New broadcast from {sender}.",
            "I should inform you. A broadcast message has arrived from {sender}.",
        ):
            cfg["announceBroadcastTemplate"] = HAL9000_TEMPLATES["broadcast"]
        if not cfg.get("announceVariants"):
            cfg["announceVariants"] = list(HAL9000_VARIANTS["direct"])
        if not cfg.get("announceBroadcastVariants"):
            cfg["announceBroadcastVariants"] = list(HAL9000_VARIANTS["broadcast"])
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
    """Speaks short SideNotes notifications — one voice, conversational pace."""

    def __init__(
        self,
        rate: int | None = None,
        volume: int | None = None,
        voice_hint: str = "",
        *,
        voice_style: str = "",
        processed_audio: bool | None = None,
        music_ducker: MusicDucker | None = None,
        neural_tts: bool = True,
        neural_python: str = "",
    ) -> None:
        _ = processed_audio  # legacy config — ignored; no WAV slowdown chain
        style = voice_style.strip().lower()
        if rate is None:
            rate = HAL_VOICE_PRESET["rate"]
        if volume is None:
            volume = HAL_VOICE_PRESET["volume"]
        if style in ("hal9000", "hal", ""):
            voice_hint = voice_hint or HAL_VOICE_PRESET["voice_hint"]

        self._voice_style = style or "hal"
        self._music_ducker = music_ducker
        self._neural_tts = bool(neural_tts)
        self._neural_python = str(neural_python or "").strip()
        self._last_engine = ""
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
        return self._voice_style or "hal"

    @property
    def last_engine(self) -> str:
        return self._last_engine or "unknown"

    def _select_voice(self, hint: str) -> None:
        try:
            voices = self._voice.GetVoices()
            hint_l = hint.lower()
            for i in range(voices.Count):
                token = voices.Item(i)
                if hint_l in token.GetDescription().lower():
                    self._voice.Voice = token
                    return
            for i in range(voices.Count):
                token = voices.Item(i)
                desc = token.GetDescription().lower()
                if "english" in desc and ("david" in desc or "mark" in desc or "guy" in desc or "male" in desc):
                    self._voice.Voice = token
                    return
        except Exception:
            pass

    def speak(self, text: str, asynchronous: bool = False) -> None:
        # Speak short cue + message-box text only. Reject origin lines / UI chrome.
        cleaned = " ".join(str(text or "").split()).strip()
        if not cleaned:
            return
        body = re.sub(
            r"(?i)^(knock knock|psst|plot twist|oh hey|got tea|hot tip|incoming charm|"
            r"listen up|quick gossip|fun one|bluenote|heads up|quick note|incoming|office message)\.\s*",
            "",
            cleaned,
        ).strip()
        if not body or is_ui_script_text(body):
            return
        if re.match(r"(?i)^(message|broadcast)\s+from\b", body):
            # Origin-only lines are not message-box content.
            return
        # Cap to message-box size.
        if len(cleaned.split()) > 48 or len(cleaned) > 260:
            cleaned = " ".join(cleaned.split()[:40])
            if cleaned[-1] not in ".!?":
                cleaned += "."
        phrase = cleaned
        with AnnounceSpeakLock() as lock:
            if not lock.acquired:
                return
            if self._music_ducker is not None:
                asynchronous = False
                self._music_ducker.duck()
            try:
                if self._neural_tts and self._speak_neural(phrase):
                    return
                self._last_engine = "sapi"
                self._speak_sapi(phrase, asynchronous=asynchronous)
            finally:
                if self._music_ducker is not None:
                    self._music_ducker.restore()

    def _speak_neural(self, text: str) -> bool:
        try:
            from neural_tts_bridge import speak_via_neural_python

            if speak_via_neural_python(
                text,
                voice="hal",
                explicit_python=self._neural_python,
            ):
                self._last_engine = "edge-neural"
                return True
        except Exception:
            pass

        try:
            root = Path(__file__).resolve().parent.parent
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from hal_tts import neural_tts_available, synthesize_text_sync

            if neural_tts_available():
                audio = synthesize_text_sync(text, {"voice": "hal"})
                if self._play_mp3(audio):
                    self._last_engine = "edge-neural-inline"
                    return True
        except Exception:
            pass
        return False

    def _play_mp3_mci(self, path: str) -> bool:
        """Play MP3 via Windows MCI — winsound only handles WAV."""
        if sys.platform != "win32":
            return False
        import ctypes

        winmm = ctypes.windll.winmm
        alias = f"halsn{os.getpid()}"
        buf = ctypes.create_unicode_buffer(255)
        mci_path = path.replace("\\", "\\\\")
        if winmm.mciSendStringW(f'open "{mci_path}" type mpegvideo alias {alias}', buf, 255, None) != 0:
            return False
        try:
            return winmm.mciSendStringW(f"play {alias} wait", buf, 255, None) == 0
        finally:
            winmm.mciSendStringW(f"close {alias}", None, 0, None)

    def _play_mp3(self, data: bytes) -> bool:
        if not data:
            return False
        path = ""
        try:
            fd, path = tempfile.mkstemp(prefix="hal_sn_", suffix=".mp3")
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
                return True
            except Exception:
                pass
            if self._play_mp3_mci(path):
                return True
            # Last resort: WAV-only API — do not claim success for MP3.
            return False
        except Exception:
            return False
        finally:
            if path:
                try:
                    os.remove(path)
                except OSError:
                    pass

    def _speak_sapi(self, text: str, asynchronous: bool = False) -> None:
        flags = SVSFlagsAsync if asynchronous else 0
        try:
            self._voice.Speak(text, flags)
        except Exception:
            pass


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
        target = 0 if not self._was_muted else 1
        for session in self._sessions():
            try:
                self._simple_volume(session).SetMute(target, None)
            except Exception:
                pass


def hal_test_phrase() -> str:
    return "HAL is online and ready."


if __name__ == "__main__":
    import json

    HERE = Path(__file__).resolve().parent
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))

    if "--neural-status" in sys.argv:
        from neural_tts_bridge import neural_tts_status

        print(json.dumps(neural_tts_status(), indent=2))
        raise SystemExit(0)

    a = Announcer(voice_style="hal9000")
    phrase = hal_test_phrase()
    a.speak(phrase)
    print(f"spoke ({a.voice_style}, {a.last_engine}): {phrase}")
    if "--mute" in sys.argv:
        b = BellController()
        print("muted:", b.mute())
