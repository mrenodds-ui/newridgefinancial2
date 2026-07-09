"""
HAL SideNotes watcher — local helper (no network, no backend service).

Watches the SideNotesIM `history.vdb` for newly-arrived messages, and for each
new incoming message:

  * announces the SENDER via Windows SAPI ("New message from <sender>"),
  * optionally suppresses the SideNotesIM bell (per-app mute) so HAL's voice
    is the alert,
  * writes a routing-only record to a JSON inbox that the HAL UI reads.

Privacy: the message body (`dMessage`) is never read. Only sender / recipient /
id / timestamp / unread flag leave SideNotesIM, and they stay on this machine.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from vdb_reader import SideNotesReader  # noqa: E402

DEFAULT_INBOX = HERE.parent / "site" / "data" / "sidenotes-inbox.json"
STATE_PATH = HERE / "watcher_state.json"
WATCHER_PID_PATH = HERE / "sidenotes-watcher.pid"
_WATCHER_MUTEX_HANDLE = None


def acquire_watcher_instance() -> bool:
    """Only one SideNotes watcher per user session (workstation + bat both start it)."""
    global _WATCHER_MUTEX_HANDLE
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        ERROR_ALREADY_EXISTS = 183
        _WATCHER_MUTEX_HANDLE = kernel32.CreateMutexW(None, True, "Local\\NR2SideNotesWatcher")
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            if _WATCHER_MUTEX_HANDLE:
                kernel32.CloseHandle(_WATCHER_MUTEX_HANDLE)
            _WATCHER_MUTEX_HANDLE = None
            return False
    try:
        WATCHER_PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        pass
    return True


def release_watcher_instance() -> None:
    global _WATCHER_MUTEX_HANDLE
    try:
        if WATCHER_PID_PATH.is_file() and int(WATCHER_PID_PATH.read_text(encoding="utf-8").strip()) == os.getpid():
            WATCHER_PID_PATH.unlink(missing_ok=True)
    except (ValueError, OSError):
        pass
    if sys.platform == "win32" and _WATCHER_MUTEX_HANDLE:
        import ctypes

        ctypes.windll.kernel32.CloseHandle(_WATCHER_MUTEX_HANDLE)
        _WATCHER_MUTEX_HANDLE = None


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def station_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return slug or "unknown"


def load_config() -> dict:
    cfg_path = HERE / "config.json"
    cfg = {}
    if cfg_path.is_file():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception as exc:
            log(f"config parse error, using defaults: {exc}")
    cfg.setdefault("historyPath", "")
    if not cfg["historyPath"]:
        cfg["historyPath"] = os.path.join(os.environ.get("APPDATA", ""), "SideNotesIM", "history.vdb")
    cfg.setdefault("simDir", r"C:\Program Files (x86)\SideNotesIM")
    cfg.setdefault("myStation", "Server")
    env_station = os.environ.get("NR2_SIDENOTES_MY_STATION", "").strip()
    if env_station:
        cfg["myStation"] = env_station
    cfg.setdefault("pollSeconds", 2.0)
    cfg.setdefault("announce", True)
    cfg.setdefault("announceTemplate", "New message from {sender}.")
    cfg.setdefault("announceBroadcastTemplate", "New broadcast from {sender}.")
    cfg.setdefault("announceScope", "to_me_or_everyone")  # or "all"
    cfg.setdefault("suppressBell", False)
    cfg.setdefault("voiceStyle", "hal9000")
    cfg.setdefault("voiceHint", "")
    cfg.setdefault("voiceRate", 3)
    cfg.setdefault("voiceVolume", 100)
    cfg.setdefault("processedAudio", False)
    cfg.setdefault("neuralTts", True)
    cfg.setdefault("neuralPython", "")
    cfg.setdefault("announceVaried", True)
    cfg.setdefault("announceVariants", [])
    cfg.setdefault("announceBroadcastVariants", [])
    cfg.setdefault(
        "stationPeople",
        {
            "room 1": "",
            "room 2": "Mayci",
            "room 3": "Nicole",
            "room 4": "Nicole",
            "room 5": "Nicole",
            "frontdesk 1": "Andrea and Jeannie",
            "frontdesk 2": "Andrea and Jeannie",
            "office manager": "Steve",
            "server": "",
            "darkroom": "",
        },
    )
    cfg.setdefault("duckMusic", True)
    cfg.setdefault("duckMusicProcesses", ["Pandora.exe"])
    cfg.setdefault("duckMusicLevel", 0.14)
    cfg.setdefault("inboxPath", "")
    if not cfg["inboxPath"]:
        cfg["inboxPath"] = str(DEFAULT_INBOX)
    cfg.setdefault("stationInboxPath", "")
    if not cfg["stationInboxPath"]:
        inbox_dir = Path(cfg["inboxPath"]).parent
        cfg["stationInboxPath"] = str(inbox_dir / f"sidenotes-inbox-{station_slug(cfg['myStation'])}.json")
    cfg.setdefault("inboxMax", 50)
    from announcer import apply_voice_style

    return apply_voice_style(cfg)


def load_state() -> dict:
    if STATE_PATH.is_file():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"lastRowId": 0, "seenIds": []}


def save_state(state: dict) -> None:
    try:
        STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:
        log(f"state save error: {exc}")


def is_for_me(note, my_station: str, scope: str) -> bool:
    if scope == "all":
        return True
    recipient = (note.recipient or "").strip().lower()
    return recipient in ("everyone", my_station.strip().lower())


def is_broadcast(note) -> bool:
    return (note.recipient or "").strip().lower() == "everyone"


def normalize_station(value: str) -> str:
    return " ".join(str(value or "").replace("_", " ").replace("-", " ").lower().split())


def station_person(station: str, cfg: dict) -> str:
    station_key = normalize_station(station)
    people = cfg.get("stationPeople") or {}
    if not isinstance(people, dict):
        return ""
    for key, person in people.items():
        if normalize_station(key) == station_key:
            return str(person).strip()
    return ""


def station_label(station: str, cfg: dict) -> str:
    station_text = str(station or "").strip()
    person = station_person(station_text, cfg)
    if not person:
        return station_text
    return f"{person} in {station_text}"


def announcement_name(note, cfg: dict) -> str:
    """Resolve a person name for HAL's spoken sender-only announcement.

    We still do not read message text. This only maps SideNotes station routing
    metadata (Room 2, Frontdesk 1, etc.) to office names the user provided.
    """
    sender_label = station_label(note.sender, cfg)
    if sender_label:
        return sender_label
    return station_label(note.recipient, cfg) or "Unknown"


def write_inbox(inbox_path: str, items: list[dict], monitor: dict) -> None:
    payload = {
        "meta": {"schema": "nr2-sidenotes-inbox-v1", "source": "SideNotesIM", "localOnly": True},
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "monitor": monitor,
        "items": items,
    }
    try:
        path = Path(inbox_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except Exception as exc:
        log(f"inbox write error: {exc}")


def write_inboxes(cfg: dict, items: list[dict], monitor: dict) -> None:
    paths = [cfg["inboxPath"], cfg.get("stationInboxPath", "")]
    written: set[str] = set()
    for path in paths:
        if not path:
            continue
        norm = os.path.normcase(os.path.abspath(path))
        if norm in written:
            continue
        written.add(norm)
        write_inbox(path, items, monitor)


def main() -> int:
    if not acquire_watcher_instance():
        log("Another SideNotes watcher is already running — exiting (only one instance allowed).")
        return 0

    cfg = load_config()
    log("HAL SideNotes watcher starting (local only; message body never read).")
    log(f"history: {cfg['historyPath']}")
    log(f"inbox:   {cfg['inboxPath']}")
    log(f"station: {cfg['stationInboxPath']}")

    if not os.path.isfile(cfg["historyPath"]):
        log("ERROR: history.vdb not found. Is SideNotesIM installed for this user?")
        return 1

    reader = SideNotesReader(history_path=cfg["historyPath"], sim_dir=cfg["simDir"])

    music_ducker = None
    if cfg.get("duckMusic"):
        try:
            from announcer import MusicDucker

            music_ducker = MusicDucker(
                process_names=cfg.get("duckMusicProcesses") or ["Pandora.exe"],
                duck_level=float(cfg.get("duckMusicLevel", 0.14)),
            )
            log(f"music ducking: ON ({', '.join(cfg.get('duckMusicProcesses') or ['Pandora.exe'])})")
        except Exception as exc:
            log(f"music ducking failed: {exc}")

    announcer = None
    if cfg["announce"]:
        try:
            from announcer import Announcer

            announcer = Announcer(
                rate=cfg["voiceRate"],
                volume=cfg["voiceVolume"],
                voice_hint=cfg["voiceHint"],
                voice_style=cfg.get("voiceStyle", ""),
                processed_audio=cfg.get("processedAudio", False),
                music_ducker=music_ducker,
                neural_tts=cfg.get("neuralTts", True),
                neural_python=str(cfg.get("neuralPython") or ""),
            )
            engine_hint = "edge-neural via 64-bit Python" if cfg.get("neuralTts", True) else "sapi"
            try:
                from neural_tts_bridge import neural_tts_status

                status = neural_tts_status(str(cfg.get("neuralPython") or ""))
                if status.get("ok"):
                    engine_hint = f"edge-neural ({status.get('voice', 'Guy')})"
                elif cfg.get("neuralTts", True):
                    engine_hint = "sapi fallback (neural unavailable)"
            except Exception:
                pass
            log(f"voice announcements: ON ({announcer.voice_style}, {engine_hint})")
        except Exception as exc:
            log(f"voice init failed (continuing without TTS): {exc}")

    bell = None
    if cfg["suppressBell"]:
        try:
            from announcer import BellController

            bell = BellController()
            log(f"bell suppression: ON (muted={bell.mute()})")
        except Exception as exc:
            log(f"bell suppression failed: {exc}")

    state = load_state()
    # On first run, baseline to the current newest message so we do not announce
    # the entire backlog.
    try:
        top = reader.max_row_id()
    except Exception as exc:
        log(f"initial read failed: {exc}")
        top = 0
    if state.get("lastRowId", 0) <= 0:
        state["lastRowId"] = top
        save_state(state)
        log(f"baseline RowId set to {top} (existing history will not be announced).")

    inbox_items: list[dict] = []
    seen_ids = set(state.get("seenIds", []))
    last_mtime = 0.0
    last_heartbeat = 0.0
    heartbeat_seconds = 15.0
    poll = float(cfg["pollSeconds"])

    def current_monitor() -> dict:
        return {
            "checkedAt": datetime.now(timezone.utc).isoformat(),
            "lastRowId": state["lastRowId"],
            "announce": bool(announcer),
            "bellSuppressed": bool(bell),
            "station": cfg["myStation"],
            "status": "live",
            "voiceStyle": announcer.voice_style if announcer else cfg.get("voiceStyle", ""),
            "duckMusic": bool(music_ducker),
        }

    # Write an initial inbox so the HAL UI immediately reflects "helper live".
    write_inboxes(cfg, inbox_items, current_monitor())
    last_heartbeat = time.monotonic()
    log("watching for new messages... (Ctrl+C to stop)")

    try:
        while True:
            try:
                mtime = os.path.getmtime(cfg["historyPath"])
            except OSError:
                mtime = last_mtime
            if mtime != last_mtime:
                last_mtime = mtime
                # File changed; re-read tail and refresh the bell mute if needed.
                if bell is not None:
                    bell.mute()
                try:
                    new_notes = reader.read_new(state["lastRowId"])
                except Exception as exc:
                    log(f"read error (will retry): {exc}")
                    new_notes = []

                for note in new_notes:
                    state["lastRowId"] = max(state["lastRowId"], note.rowId)
                    if note.messageId and note.messageId in seen_ids:
                        continue
                    if note.messageId:
                        seen_ids.add(note.messageId)
                    # Skip our own outgoing messages.
                    if note.sender.strip().lower() == cfg["myStation"].strip().lower():
                        continue
                    if not is_for_me(note, cfg["myStation"], cfg["announceScope"]):
                        continue

                    sender_label = station_label(note.sender, cfg)
                    recipient_label = station_label(note.recipient, cfg)
                    item = {
                        "id": note.messageId or f"row{note.rowId}",
                        "rowId": note.rowId,
                        "sender": note.sender,
                        "senderLabel": sender_label,
                        "recipient": note.recipient,
                        "recipientLabel": recipient_label,
                        "broadcast": is_broadcast(note),
                        "date": note.date,
                        "time": note.time,
                        "unread": note.unread,
                        "capturedAt": datetime.now(timezone.utc).isoformat(),
                    }
                    inbox_items.append(item)
                    inbox_items[:] = inbox_items[-int(cfg["inboxMax"]):]

                    log(f"NEW from '{note.sender}' to '{note.recipient}' ({note.date} {note.time})")
                    if announcer is not None:
                        sender_name = announcement_name(note, cfg)
                        if cfg.get("announceVaried", True):
                            from announcer import pick_announcement

                            phrase = pick_announcement(sender_name, item["broadcast"], cfg)
                        else:
                            tmpl = cfg["announceBroadcastTemplate"] if item["broadcast"] else cfg["announceTemplate"]
                            phrase = tmpl.format(sender=sender_name)
                        announcer.speak(phrase)

                state["seenIds"] = list(seen_ids)[-500:]
                save_state(state)
                write_inboxes(cfg, inbox_items, current_monitor())
                last_heartbeat = time.monotonic()

            # Heartbeat: refresh checkedAt periodically so the HAL UI can tell a
            # running watcher from a stale inbox file left by a stopped one.
            if time.monotonic() - last_heartbeat >= heartbeat_seconds:
                write_inboxes(cfg, inbox_items, current_monitor())
                last_heartbeat = time.monotonic()
            time.sleep(poll)
    except KeyboardInterrupt:
        log("stopping...")
    finally:
        if bell is not None:
            bell.restore()
            log("bell mute restored.")
        release_watcher_instance()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
