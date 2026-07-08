"""Bridge 32-bit SideNotes watcher to 64-bit HAL neural TTS."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HELPER_DIR = Path(__file__).resolve().parent
NR2_ROOT = HELPER_DIR.parent
REPO_ROOT = NR2_ROOT.parent
CLI = NR2_ROOT / "hal_tts_cli.py"

_CACHED_PYTHON: Path | None = None
_CACHED_STATUS: dict[str, Any] | None = None


def _subprocess_kwargs() -> dict:
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return kwargs


def _python_cmd(python: Path, *args: str) -> list[str]:
    cmd = [str(python)]
    if python.name.lower() in ("py.exe", "py"):
        cmd.append("-3")
    cmd.extend(args)
    return cmd


def _parse_json_stdout(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        pass
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    return {}


def resolve_neural_python(explicit: str = "") -> Path | None:
    """Find a 64-bit Python with edge-tts for HAL neural voice."""
    global _CACHED_PYTHON
    if _CACHED_PYTHON and _CACHED_PYTHON.is_file():
        return _CACHED_PYTHON

    candidates: list[Path] = []
    for raw in (
        explicit,
        os.environ.get("NR2_NEURAL_PYTHON", ""),
        os.environ.get("NR2_PYTHON", ""),
    ):
        if raw:
            candidates.append(Path(raw))

    candidates.extend(
        [
            REPO_ROOT / ".venv" / "Scripts" / "python.exe",
            REPO_ROOT / ".venv-py313" / "Scripts" / "python.exe",
            NR2_ROOT / ".venv" / "Scripts" / "python.exe",
        ]
    )

    seen: set[str] = set()
    for path in candidates:
        if not path or not path.is_file():
            continue
        key = os.path.normcase(str(path.resolve()))
        if key in seen:
            continue
        seen.add(key)
        if _python_has_neural(path):
            _CACHED_PYTHON = path
            return path

    for launcher in ("py", "python3", "python"):
        found = _which_launcher(launcher)
        if found and _python_has_neural(found):
            _CACHED_PYTHON = found
            return found
    return None


def _which_launcher(name: str) -> Path | None:
    try:
        proc = subprocess.run(
            ["where", name] if sys.platform == "win32" else ["which", name],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
            **_subprocess_kwargs(),
        )
        line = (proc.stdout or "").strip().splitlines()
        if not line:
            return None
        path = Path(line[0].strip())
        return path if path.is_file() else None
    except Exception:
        return None


def _python_has_neural(python: Path) -> bool:
    if not CLI.is_file():
        return False
    try:
        proc = subprocess.run(
            _python_cmd(python, str(CLI), "status"),
            cwd=str(NR2_ROOT),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            **_subprocess_kwargs(),
        )
        if proc.returncode != 0:
            return False
        return bool(_parse_json_stdout(proc.stdout or "").get("ok"))
    except Exception:
        return False


def neural_tts_status(explicit_python: str = "") -> dict[str, Any]:
    global _CACHED_STATUS
    python = resolve_neural_python(explicit_python)
    if not python:
        return {"ok": False, "engine": "edge-neural", "error": "no 64-bit neural python"}
    if _CACHED_STATUS and _CACHED_STATUS.get("python") == str(python):
        return dict(_CACHED_STATUS)

    try:
        proc = subprocess.run(
            _python_cmd(python, str(CLI), "status"),
            cwd=str(NR2_ROOT),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            **_subprocess_kwargs(),
        )
        data = _parse_json_stdout(proc.stdout or "")
        if not data:
            data = {"ok": False, "error": "invalid status response"}
        data["python"] = str(python)
        _CACHED_STATUS = data
        return dict(data)
    except Exception as exc:
        return {"ok": False, "engine": "edge-neural", "python": str(python), "error": str(exc)}


def speak_via_neural_python(
    text: str,
    *,
    voice: str = "hal",
    explicit_python: str = "",
    timeout: float = 120.0,
) -> bool:
    """Synthesize and play via external 64-bit Python. Returns True on success."""
    phrase = str(text or "").strip()
    if not phrase or not CLI.is_file():
        return False
    python = resolve_neural_python(explicit_python)
    if not python:
        return False
    try:
        proc = subprocess.run(
            _python_cmd(python, str(CLI), "speak", "--text", phrase, "--voice", voice or "hal"),
            cwd=str(NR2_ROOT),
            capture_output=True,
            text=True,
            timeout=float(timeout),
            check=False,
            **_subprocess_kwargs(),
        )
        if proc.returncode != 0:
            return False
        return bool(_parse_json_stdout(proc.stdout or "").get("ok"))
    except Exception:
        return False
