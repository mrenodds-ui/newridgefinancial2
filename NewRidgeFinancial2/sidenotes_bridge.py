"""Bridge NR2 desktop (64-bit) to SideNotesIM helper (32-bit py32)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HELPER_DIR = ROOT / "sidenotes-helper"
PY32 = HELPER_DIR / "py32" / "python.exe"
CLI = HELPER_DIR / "sidenotes_cli.py"
WATCHER = HELPER_DIR / "sidenotes_watcher.py"
WATCHER_PID_PATH = HELPER_DIR / "sidenotes-watcher.pid"
WATCHER_STATE_PATH = HELPER_DIR / "sidenotes-watcher-state.json"


def _read_watcher_state() -> dict:
    if not WATCHER_STATE_PATH.is_file():
        return {}
    try:
        data = json.loads(WATCHER_STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_watcher_state(state: dict) -> None:
    try:
        WATCHER_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:
        pass


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


def sidenotes_watcher_pid() -> int | None:
    if not WATCHER_PID_PATH.is_file():
        return None
    try:
        pid = int(WATCHER_PID_PATH.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None
    if pid <= 0:
        return None
    if not _pid_alive(pid):
        return None
    return pid


def sidenotes_watcher_running() -> bool:
    return sidenotes_watcher_pid() is not None


def _terminate_watcher_pid(pid: int) -> None:
    if pid <= 0:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                check=False,
                **_subprocess_run_kwargs(),
            )
        else:
            os.kill(pid, 15)
    except OSError:
        pass
    try:
        WATCHER_PID_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def sidenotes_watcher_health() -> dict:
    pid = sidenotes_watcher_pid()
    state = _read_watcher_state()
    cli = _run_cli(["status"], timeout=12.0)
    history_ok = bool(cli.get("historyExists") or cli.get("ok"))
    return {
        "watcherRunning": pid is not None,
        "watcherPid": pid,
        "historyExists": history_ok,
        "cliOk": bool(cli.get("ok")),
        "restartCount": int(state.get("restartCount") or 0),
        "lastRestartAt": state.get("lastRestartAt"),
        "lastCheckAt": datetime.now(timezone.utc).isoformat(),
    }


def ensure_sidenotes_watcher(station: str | None = None, force_restart: bool = False) -> dict:
    station = (station or os.environ.get("NR2_SIDENOTES_MY_STATION", "").strip() or None)
    pid = sidenotes_watcher_pid()
    state = _read_watcher_state()

    if force_restart and pid:
        _terminate_watcher_pid(pid)
        pid = None

    if pid:
        return {
            "ok": True,
            "action": "already_running",
            "pid": pid,
            "restartCount": int(state.get("restartCount") or 0),
        }

    if not WATCHER.is_file():
        return {"ok": False, "action": "missing_watcher", "error": "sidenotes_watcher.py not found"}

    proc = start_sidenotes_watcher(station)
    if proc is None:
        return {"ok": False, "action": "start_failed", "error": "could not spawn sidenotes watcher"}

    state["restartCount"] = int(state.get("restartCount") or 0) + 1
    state["lastRestartAt"] = datetime.now(timezone.utc).isoformat()
    _write_watcher_state(state)
    return {
        "ok": True,
        "action": "started",
        "pid": proc.pid,
        "restartCount": state["restartCount"],
    }


def _python_cmd() -> list[str]:
    if PY32.is_file():
        return [str(PY32), str(CLI)]
    return [sys.executable, str(CLI)]


def _subprocess_run_kwargs() -> dict:
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return kwargs


def _run_cli(args: list[str], timeout: float = 45.0) -> dict:
    cmd = _python_cmd() + args
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(HELPER_DIR),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            **_subprocess_run_kwargs(),
        )
        raw = (proc.stdout or "").strip()
        if not raw and proc.stderr:
            return {"ok": False, "error": proc.stderr.strip()}
        if not raw:
            return {"ok": False, "error": f"empty cli response (exit {proc.returncode})"}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {"ok": False, "error": raw, "stderr": proc.stderr.strip()}
        if proc.returncode != 0 and data.get("ok") is not False:
            data["ok"] = False
            data.setdefault("error", proc.stderr.strip() or f"exit {proc.returncode}")
        return data
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "sidenotes cli timeout"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def sidenotes_status() -> dict:
    data = _run_cli(["status"])
    data["watcher"] = sidenotes_watcher_health()
    return data


def sidenotes_read_messages(station: str = "", limit: int = 48, include_body: bool = True) -> dict:
    args = ["read", "--limit", str(int(limit)), "--include-body"]
    if station:
        args.extend(["--station", str(station)])
    return _run_cli(args)


def sidenotes_send_message(from_station: str, to_station: str, text: str) -> dict:
    args = [
        "send",
        "--from-station",
        str(from_station or "").strip(),
        "--to",
        str(to_station or "Everyone").strip(),
        "--text",
        str(text or "").strip(),
    ]
    return _run_cli(args, timeout=60.0)


def start_sidenotes_watcher(station: str | None = None) -> subprocess.Popen | None:
    if not WATCHER.is_file():
        return None
    existing = sidenotes_watcher_pid()
    if existing:
        return None
    python = PY32 if PY32.is_file() else Path(sys.executable)
    env = os.environ.copy()
    if station:
        env["NR2_SIDENOTES_MY_STATION"] = str(station)
    try:
        return subprocess.Popen(
            [str(python), str(WATCHER)],
            cwd=str(HELPER_DIR),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return None
