"""HAL BlueNote watcher — announce BlueNote events with program HAL neural voice.

Replaces SideNotesIM polling. Reads routing metadata only (never message bodies).
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Prefer real NR2 tree; SoftDent package copies land under C:\softdent\HAL-BlueNote-Workstation\.
_repo_env = os.environ.get("NEWRIDGE_FINANCIAL_REPO", "").strip()
_nr2_env = os.environ.get("NR2_ROOT", "").strip()
if _nr2_env and Path(_nr2_env).is_dir():
    NR2 = Path(_nr2_env)
elif _repo_env and (Path(_repo_env) / "NewRidgeFinancial2").is_dir():
    NR2 = Path(_repo_env) / "NewRidgeFinancial2"
elif (HERE.parent / "sidenotes-helper" / "announcer.py").is_file():
    NR2 = HERE.parent
else:
    NR2 = HERE
# Reuse neural HAL announcer from sidenotes-helper (same ChristopherNeural path).
SIDENOTES_HELPER = NR2 / "sidenotes-helper"
if not (SIDENOTES_HELPER / "announcer.py").is_file():
    SIDENOTES_HELPER = HERE
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SIDENOTES_HELPER))

from bluenote_reader import (  # noqa: E402
    DEFAULT_ROAMING,
    bluenote_running,
    read_panel_name,
    scan_events,
)

STATE_PATH = HERE / "watcher_state.json"
PID_PATH = HERE / "bluenote-watcher.pid"
# Keep sidenotes-inbox.json filename so NR2 desktop/hub readers stay compatible.
DEFAULT_INBOX = NR2 / "site" / "data" / "sidenotes-inbox.json"
CONFIG_PATH = HERE / "config.json"
_WATCHER_MUTEX_HANDLE = None


def acquire_watcher_instance() -> bool:
    """Only one BlueNote watcher per user session."""
    global _WATCHER_MUTEX_HANDLE
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        ERROR_ALREADY_EXISTS = 183
        _WATCHER_MUTEX_HANDLE = kernel32.CreateMutexW(None, True, "Local\\NR2BlueNoteWatcher")
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            if _WATCHER_MUTEX_HANDLE:
                kernel32.CloseHandle(_WATCHER_MUTEX_HANDLE)
            _WATCHER_MUTEX_HANDLE = None
            return False
    try:
        PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        pass
    return True


def release_watcher_instance() -> None:
    global _WATCHER_MUTEX_HANDLE
    try:
        if PID_PATH.is_file() and int(PID_PATH.read_text(encoding="utf-8").strip()) == os.getpid():
            PID_PATH.unlink(missing_ok=True)
    except (ValueError, OSError):
        pass
    if sys.platform == "win32" and _WATCHER_MUTEX_HANDLE:
        import ctypes

        ctypes.windll.kernel32.CloseHandle(_WATCHER_MUTEX_HANDLE)
        _WATCHER_MUTEX_HANDLE = None


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def station_slug(value: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return slug or "unknown"


def load_config() -> dict:
    cfg: dict = {}
    if CONFIG_PATH.is_file():
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            log(f"config parse error: {exc}")
    env_station = (
        os.environ.get("NR2_BLUENOTE_MY_STATION", "").strip()
        or os.environ.get("NR2_SIDENOTES_MY_STATION", "").strip()
    )
    panel = env_station or read_panel_name() or str(cfg.get("myStation") or "").strip() or "This station"
    cfg["myStation"] = panel
    # Treat blank config strings as unset so defaults apply.
    for key in ("inboxPath", "stationInboxPath", "neuralPython", "myStation"):
        if not str(cfg.get(key) or "").strip():
            cfg.pop(key, None)
    cfg["myStation"] = panel
    cfg.setdefault("pollSeconds", 1.5)
    cfg.setdefault("announce", True)
    cfg.setdefault("voiceStyle", "hal9000")
    cfg.setdefault("neuralTts", True)
    cfg.setdefault("neuralPython", os.environ.get("NR2_NEURAL_PYTHON", ""))
    cfg.setdefault("announceConversations", True)
    cfg.setdefault("announceLights", False)
    cfg.setdefault("announceInboxBump", True)
    cfg.setdefault("quietBootstrap", True)
    cfg.setdefault("duckMusic", True)
    cfg.setdefault("duckMusicProcesses", ["Pandora.exe"])
    cfg.setdefault("duckMusicLevel", 0.14)
    cfg.setdefault("inboxPath", str(DEFAULT_INBOX))
    cfg.setdefault(
        "stationInboxPath",
        str(Path(cfg["inboxPath"]).parent / f"sidenotes-inbox-{station_slug(cfg['myStation'])}.json"),
    )
    # SoftDent hub package path (shared with HAL workstation data folder).
    hub_data = os.environ.get("NR2_SIDENOTES_HUB_DATA", "").strip() or os.environ.get(
        "NR2_BLUENOTE_HUB_DATA", ""
    ).strip()
    if not hub_data:
        hub_data = r"C:\softdent\HAL-BlueNote-Workstation\data"
    cfg["hubInboxPath"] = str(Path(hub_data) / "sidenotes-inbox.json")
    cfg["hubStationInboxPath"] = str(
        Path(hub_data) / f"sidenotes-inbox-{station_slug(cfg['myStation'])}.json"
    )
    cfg.setdefault("inboxMax", 50)
    cfg.setdefault(
        "stationPeople",
        {
            "frontdesk 1": "Andrea and Jeannie",
            "frontdesk 2": "Andrea and Jeannie",
            "office manager": "Steve",
            "room 1": "",
            "room 2": "Mayci",
            "room 3": "Nicole",
            "room 4": "Nicole",
            "room 5": "Nicole",
            "server": "",
            "dr. reno": "Dr. Reno",
        },
    )
    from announcer import apply_voice_style

    return apply_voice_style(cfg)


def load_state() -> dict:
    if STATE_PATH.is_file():
        try:
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("seenIds", [])
                data.setdefault("inboxCount", None)
                data.setdefault("econMtime", None)
                return data
        except Exception:
            pass
    return {"seenIds": [], "inboxCount": None, "econMtime": None}


def save_state(state: dict) -> None:
    try:
        STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:
        log(f"state save error: {exc}")


def write_pid() -> None:
    try:
        PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        pass


def normalize_station(value: str) -> str:
    return " ".join(str(value or "").replace("_", " ").replace("-", " ").lower().split())


def station_person(station: str, cfg: dict) -> str:
    people = cfg.get("stationPeople") or {}
    if not isinstance(people, dict):
        return ""
    key = normalize_station(station)
    for k, person in people.items():
        if normalize_station(k) == key:
            return str(person).strip()
    return ""


def announcement_name(sender: str, cfg: dict) -> str:
    person = station_person(sender, cfg)
    if person:
        return person
    return str(sender or "BlueNote").strip() or "BlueNote"


def write_inbox(inbox_path: str, items: list[dict], monitor: dict) -> None:
    path = Path(inbox_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": {
            "schema": "nr2-sidenotes-inbox-v1",
            "source": "BlueNote",
            "localOnly": True,
            "bodyNeverRead": True,
        },
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "monitor": monitor,
        "items": items[: int(monitor.get("inboxMax") or 50)],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_inboxes(cfg: dict, items: list[dict], monitor: dict) -> None:
    paths = [
        cfg.get("inboxPath"),
        cfg.get("stationInboxPath"),
        cfg.get("hubInboxPath"),
        cfg.get("hubStationInboxPath"),
    ]
    seen: set[str] = set()
    for path in paths:
        p = str(path or "").strip()
        if not p or p in seen:
            continue
        seen.add(p)
        write_inbox(p, items, monitor)


def main() -> int:
    if not acquire_watcher_instance():
        log("Another BlueNote watcher is already running — exiting (only one instance allowed).")
        return 0
    try:
        return run_watcher()
    finally:
        release_watcher_instance()


def run_watcher() -> int:
    cfg = load_config()
    write_pid()
    state = load_state()
    seen = set(str(x) for x in (state.get("seenIds") or []) if str(x).strip())
    inbox_items: list[dict] = []

    music_ducker = None
    if cfg.get("duckMusic"):
        try:
            from announcer import MusicDucker

            music_ducker = MusicDucker(
                process_names=cfg.get("duckMusicProcesses") or ["Pandora.exe"],
                duck_level=float(cfg.get("duckMusicLevel", 0.14)),
            )
        except Exception as exc:
            log(f"music ducking failed: {exc}")

    announcer = None
    if cfg.get("announce"):
        try:
            from announcer import Announcer, pick_bluenote_announcement

            announcer = Announcer(
                rate=cfg.get("voiceRate", 0),
                volume=cfg.get("voiceVolume", 100),
                voice_hint=cfg.get("voiceHint", "David"),
                voice_style=cfg.get("voiceStyle", "hal9000"),
                processed_audio=False,
                music_ducker=music_ducker,
                neural_tts=bool(cfg.get("neuralTts", True)),
                neural_python=str(cfg.get("neuralPython") or ""),
            )
            engine = "edge-neural"
            try:
                from neural_tts_bridge import neural_tts_status

                st = neural_tts_status(str(cfg.get("neuralPython") or ""))
                if st.get("ok"):
                    engine = f"edge-neural ({st.get('voice', 'Guy')})"
                else:
                    engine = "sapi fallback (neural unavailable)"
            except Exception:
                pass
            log(f"voice announcements: ON ({announcer.voice_style}, {engine})")
        except Exception as exc:
            log(f"voice init failed: {exc}")

    log(
        f"BlueNote watcher ready · station={cfg['myStation']} · "
        f"running={bluenote_running()} · roaming={DEFAULT_ROAMING}"
    )

    bootstrapped = bool(seen) or not bool(cfg.get("quietBootstrap", True))

    while True:
        try:
            snap = scan_events(my_panel=cfg["myStation"])
            monitor = {
                "ok": bool(snap.get("ok")),
                "source": "BlueNote",
                "announce": bool(cfg.get("announce")),
                "voiceStyle": cfg.get("voiceStyle"),
                "station": cfg["myStation"],
                "panelName": snap.get("panelName"),
                "inboxCount": snap.get("inboxCount"),
                "bluenoteRunning": bool(snap.get("running")),
                "checkedAt": datetime.now(timezone.utc).isoformat(),
                "inboxMax": cfg.get("inboxMax", 50),
                "bellSuppressed": True,
                "totalStations": 1,
                "stationCount": 1 if snap.get("running") else 0,
            }

            # First live scan: silence existing light-board chrome (do not read the whole script).
            if not bootstrapped and snap.get("ok"):
                for ev in snap.get("events") or []:
                    eid = str(ev.get("id") or "")
                    if eid:
                        seen.add(eid)
                if isinstance(snap.get("inboxCount"), int):
                    state["inboxCount"] = snap.get("inboxCount")
                state["seenIds"] = list(seen)[-300:]
                save_state(state)
                write_inboxes(cfg, inbox_items[: cfg.get("inboxMax", 50)], monitor)
                bootstrapped = True
                log(f"quiet bootstrap — {len(seen)} existing BlueNote cues silenced")
                time.sleep(max(0.5, float(cfg.get("pollSeconds") or 1.5)))
                continue

            # Inbox count bump → short random opener + note (no body)
            prev_inbox = state.get("inboxCount")
            cur_inbox = snap.get("inboxCount")
            if (
                cfg.get("announceInboxBump")
                and isinstance(cur_inbox, int)
                and isinstance(prev_inbox, int)
                and cur_inbox > prev_inbox
            ):
                bump_id = f"inbox-bump|{prev_inbox}->{cur_inbox}|{int(time.time())}"
                if bump_id not in seen:
                    item = {
                        "id": bump_id,
                        "sender": "BlueNote",
                        "senderLabel": "BlueNote",
                        "recipient": cfg["myStation"],
                        "recipientLabel": cfg["myStation"],
                        "broadcast": False,
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "unread": True,
                        "kind": "inbox",
                        "label": f"New BlueNote conversation ({cur_inbox} in inbox)",
                        "capturedAt": datetime.now(timezone.utc).isoformat(),
                        "sourceStation": cfg["myStation"],
                    }
                    inbox_items.insert(0, item)
                    seen.add(bump_id)
                    if announcer:
                        try:
                            from announcer import pick_bluenote_announcement

                            phrase = pick_bluenote_announcement(
                                "BlueNote",
                                broadcast=False,
                                message="New message.",
                                cfg=cfg,
                            )
                            announcer.speak(phrase)
                            log(f"announced inbox bump -> {cur_inbox} ({announcer.last_engine}): {phrase}")
                        except Exception as exc:
                            log(f"announce failed: {exc}")
            if isinstance(cur_inbox, int):
                state["inboxCount"] = cur_inbox

            for ev in snap.get("events") or []:
                eid = str(ev.get("id") or "")
                if not eid or eid in seen:
                    continue
                kind = str(ev.get("kind") or "")
                if kind == "conversation" and not cfg.get("announceConversations", True):
                    continue
                if kind == "light" and not cfg.get("announceLights", True):
                    continue
                sender = str(ev.get("sender") or "BlueNote")
                recipient = str(ev.get("recipient") or "")
                broadcast = bool(ev.get("broadcast"))
                spoken_as = announcement_name(sender, cfg)
                item = {
                    "id": eid,
                    "sender": sender,
                    "senderLabel": spoken_as,
                    "recipient": recipient,
                    "recipientLabel": recipient,
                    "broadcast": broadcast,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "unread": True,
                    "kind": kind,
                    "label": ev.get("label") or "",
                    "capturedAt": ev.get("capturedAt") or datetime.now(timezone.utc).isoformat(),
                    "sourceStation": cfg["myStation"],
                }
                inbox_items.insert(0, item)
                seen.add(eid)
                if announcer and cfg.get("announce"):
                    try:
                        from announcer import pick_bluenote_announcement

                        # Never speak BlueNote UI chrome / light scripts — opener + sender only.
                        phrase = pick_bluenote_announcement(
                            spoken_as,
                            broadcast=broadcast or kind == "light",
                            message="",
                            cfg=cfg,
                        )
                        announcer.speak(phrase)
                        log(f"announced {kind}: {phrase} ({announcer.last_engine})")
                    except Exception as exc:
                        log(f"announce failed: {exc}")

            if len(seen) > 500:
                seen = set(list(seen)[-300:])
            state["seenIds"] = list(seen)[-300:]
            state["econMtime"] = snap.get("econversationsMtime")
            save_state(state)

            write_inboxes(cfg, inbox_items[: cfg.get("inboxMax", 50)], monitor)
        except Exception as exc:
            log(f"loop error: {exc}")

        time.sleep(max(0.5, float(cfg.get("pollSeconds") or 1.5)))


if __name__ == "__main__":
    raise SystemExit(main() or 0)
