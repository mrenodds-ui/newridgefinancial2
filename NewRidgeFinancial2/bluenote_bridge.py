"""Bridge NR2 desktop to BlueNote Communicator Lights HAL watcher.

Replaces SideNotesIM watcher spawn/supervisor. Message send/read of bodies
is not supported (BlueNote stores are encrypted; privacy: routing only).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HELPER_DIR = ROOT / "bluenote-helper"
WATCHER = HELPER_DIR / "bluenote_watcher.py"
WATCHER_PID_PATH = HELPER_DIR / "bluenote-watcher.pid"
WATCHER_STATE_PATH = HELPER_DIR / "watcher_state.json"
WATCHER_SUPERVISOR_STATE = HELPER_DIR / "bluenote-watcher-supervisor.json"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, state: dict) -> None:
    try:
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:
        pass


def bluenote_watcher_pid() -> int | None:
    if not WATCHER_PID_PATH.is_file():
        return None
    try:
        pid = int(WATCHER_PID_PATH.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None
    if pid <= 0 or not _pid_alive(pid):
        return None
    return pid


def bluenote_watcher_running() -> bool:
    return bluenote_watcher_pid() is not None


def _terminate_watcher_pid(pid: int) -> None:
    if pid <= 0:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            os.kill(pid, 15)
    except OSError:
        pass
    try:
        WATCHER_PID_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def bluenote_watcher_health() -> dict:
    pid = bluenote_watcher_pid()
    state = _read_json(WATCHER_STATE_PATH)
    supervisor = _read_json(WATCHER_SUPERVISOR_STATE)
    running_bn = False
    panel = ""
    try:
        sys.path.insert(0, str(HELPER_DIR))
        from bluenote_reader import bluenote_running, read_panel_name

        running_bn = bluenote_running()
        panel = read_panel_name() or ""
    except Exception:
        pass
    return {
        "watcherRunning": pid is not None,
        "watcherPid": pid,
        "bluenoteRunning": running_bn,
        "panelName": panel,
        "inboxCount": state.get("inboxCount"),
        "restartCount": int(supervisor.get("restartCount") or 0),
        "lastRestartAt": supervisor.get("lastRestartAt"),
        "lastCheckAt": datetime.now(timezone.utc).isoformat(),
        "source": "BlueNote",
    }


def start_bluenote_watcher(station: str | None = None) -> subprocess.Popen | None:
    if not WATCHER.is_file():
        return None
    existing = bluenote_watcher_pid()
    if existing:
        return None
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    if station:
        env["NR2_BLUENOTE_MY_STATION"] = str(station)
        env.setdefault("NR2_SIDENOTES_MY_STATION", str(station))
    python = Path(os.environ.get("NR2_NEURAL_PYTHON") or sys.executable)
    if not python.is_file():
        python = Path(sys.executable)
    try:
        return subprocess.Popen(
            [str(python), "-u", str(WATCHER)],
            cwd=str(HELPER_DIR),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return None


def ensure_bluenote_watcher(station: str | None = None, force_restart: bool = False) -> dict:
    station = (
        station
        or os.environ.get("NR2_BLUENOTE_MY_STATION", "").strip()
        or os.environ.get("NR2_SIDENOTES_MY_STATION", "").strip()
        or None
    )
    pid = bluenote_watcher_pid()
    supervisor = _read_json(WATCHER_SUPERVISOR_STATE)

    if force_restart and pid:
        _terminate_watcher_pid(pid)
        pid = None
        # Brief pause so mutex releases.
        import time

        time.sleep(0.4)

    if pid:
        return {
            "ok": True,
            "action": "already_running",
            "pid": pid,
            "restartCount": int(supervisor.get("restartCount") or 0),
        }

    if not WATCHER.is_file():
        return {"ok": False, "action": "missing_watcher", "error": "bluenote_watcher.py not found"}

    proc = start_bluenote_watcher(station)
    if proc is None:
        return {"ok": False, "action": "start_failed", "error": "could not spawn BlueNote watcher"}

    # Venv python may re-exec; trust the PID file written by the real process.
    import time

    resolved: int | None = None
    for _ in range(20):
        time.sleep(0.15)
        resolved = bluenote_watcher_pid()
        if resolved:
            break

    supervisor["restartCount"] = int(supervisor.get("restartCount") or 0) + 1
    supervisor["lastRestartAt"] = datetime.now(timezone.utc).isoformat()
    _write_json(WATCHER_SUPERVISOR_STATE, supervisor)
    return {
        "ok": True,
        "action": "started",
        "pid": resolved or proc.pid,
        "restartCount": supervisor["restartCount"],
    }


def bluenote_status() -> dict:
    health = bluenote_watcher_health()
    return {
        "ok": True,
        "source": "BlueNote",
        "bodyNeverRead": True,
        "watcher": health,
        "panelName": health.get("panelName"),
        "bluenoteRunning": health.get("bluenoteRunning"),
    }
