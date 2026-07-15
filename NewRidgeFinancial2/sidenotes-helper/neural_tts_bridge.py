"""Bridge 32-bit SideNotes watcher to 64-bit HAL neural TTS."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HELPER_DIR = Path(__file__).resolve().parent

_CACHED_PYTHON: Path | None = None
_CACHED_STATUS: dict[str, Any] | None = None
_CACHED_NR2_ROOT: Path | None = None


def resolve_nr2_root() -> Path:
    """Find NewRidgeFinancial2 even when this helper is copied under C:\\softdent."""
    global _CACHED_NR2_ROOT
    if _CACHED_NR2_ROOT and (_CACHED_NR2_ROOT / "hal_tts_cli.py").is_file():
        return _CACHED_NR2_ROOT

    candidates: list[Path] = []
    env_repo = str(os.environ.get("NEWRIDGE_FINANCIAL_REPO") or "").strip()
    if env_repo:
        candidates.append(Path(env_repo) / "NewRidgeFinancial2")
    env_nr2 = str(os.environ.get("NR2_ROOT") or "").strip()
    if env_nr2:
        candidates.append(Path(env_nr2))

    # Normal: .../NewRidgeFinancial2/sidenotes-helper/
    candidates.append(HELPER_DIR.parent)
    # SoftDent package copies often land under C:\softdent\HAL-SideNotes-Workstation\
    candidates.extend(
        [
            Path(r"C:\Users\mreno\newridgefamilyfinancial\NewRidgeFinancial2"),
            Path(r"C:\NewRidgeFamilyFinancial\NewRidgeFinancial2"),
            Path(r"E:\NewRidgeFamilyFinancial\NewRidgeFinancial2"),
        ]
    )

    seen: set[str] = set()
    for path in candidates:
        if not path:
            continue
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        key = os.path.normcase(str(resolved))
        if key in seen:
            continue
        seen.add(key)
        if (resolved / "hal_tts_cli.py").is_file() and (resolved / "hal_tts.py").is_file():
            _CACHED_NR2_ROOT = resolved
            return resolved

    # Last resort — caller will fail status/speak clearly.
    fallback = HELPER_DIR.parent
    _CACHED_NR2_ROOT = fallback
    return fallback


def _cli_path() -> Path:
    return resolve_nr2_root() / "hal_tts_cli.py"


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

    nr2_root = resolve_nr2_root()
    repo_root = nr2_root.parent

    candidates: list[Path] = []
    for raw in (
        explicit,
        os.environ.get("NR2_NEURAL_PYTHON", ""),
        os.environ.get("NR2_PYTHON", ""),
    ):
        if raw:
            candidates.append(Path(raw))

    # Prefer workstation package / NR2 venv 64-bit Python (edge-tts lives here).
    candidates.extend(
        [
            repo_root / "python" / "Scripts" / "python.exe",
            nr2_root / "python" / "Scripts" / "python.exe",
            repo_root / ".venv" / "Scripts" / "python.exe",
            repo_root / ".venv-py313" / "Scripts" / "python.exe",
            nr2_root / ".venv" / "Scripts" / "python.exe",
            Path(r"C:\Users\mreno\newridgefamilyfinancial\.venv\Scripts\python.exe"),
            Path(r"C:\NewRidgeFamilyFinancial\.venv\Scripts\python.exe"),
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
    cli = _cli_path()
    if not cli.is_file():
        return False
    try:
        proc = subprocess.run(
            _python_cmd(python, str(cli), "status"),
            cwd=str(resolve_nr2_root()),
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
        return {
            "ok": False,
            "engine": "edge-neural",
            "error": "no 64-bit neural python",
            "nr2Root": str(resolve_nr2_root()),
            "cli": str(_cli_path()),
        }
    if _CACHED_STATUS and _CACHED_STATUS.get("python") == str(python):
        return dict(_CACHED_STATUS)

    try:
        proc = subprocess.run(
            _python_cmd(python, str(_cli_path()), "status"),
            cwd=str(resolve_nr2_root()),
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
        data["nr2Root"] = str(resolve_nr2_root())
        _CACHED_STATUS = data
        return dict(data)
    except Exception as exc:
        return {
            "ok": False,
            "engine": "edge-neural",
            "python": str(python),
            "error": str(exc),
            "nr2Root": str(resolve_nr2_root()),
        }


def speak_via_neural_python(
    text: str,
    *,
    voice: str = "hal",
    explicit_python: str = "",
    timeout: float = 120.0,
) -> bool:
    """Synthesize and play via external 64-bit Python. Returns True on success."""
    phrase = str(text or "").strip()
    cli = _cli_path()
    if not phrase or not cli.is_file():
        return False
    python = resolve_neural_python(explicit_python)
    if not python:
        return False
    try:
        proc = subprocess.run(
            _python_cmd(
                python, str(cli), "speak", "--text", phrase, "--voice", voice or "hal"
            ),
            cwd=str(resolve_nr2_root()),
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
