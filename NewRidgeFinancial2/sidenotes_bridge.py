"""Bridge NR2 desktop (64-bit) to SideNotesIM helper (32-bit py32)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HELPER_DIR = ROOT / "sidenotes-helper"
PY32 = HELPER_DIR / "py32" / "python.exe"
CLI = HELPER_DIR / "sidenotes_cli.py"
WATCHER = HELPER_DIR / "sidenotes_watcher.py"
WATCHER_PID_PATH = HELPER_DIR / "sidenotes-watcher.pid"


def sidenotes_watcher_pid() -> int | None:
    if not WATCHER_PID_PATH.is_file():
        return None
    try:
        pid = int(WATCHER_PID_PATH.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None
    if pid <= 0:
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        return None
    return pid


def sidenotes_watcher_running() -> bool:
    return sidenotes_watcher_pid() is not None


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
    return _run_cli(["status"])


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
