"""Launch a PowerShell .ps1 with CREATE_NO_WINDOW (no console flash).

Usage:
  pythonw.exe run_powershell_hidden.py "C:\\path\\script.ps1" [extra args...]
"""
from __future__ import annotations

import subprocess
import sys

CREATE_NO_WINDOW = 0x08000000


def main() -> int:
    if len(sys.argv) < 2:
        return 1
    script = sys.argv[1]
    extra = sys.argv[2:]
    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-WindowStyle",
        "Hidden",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        script,
        *extra,
    ]
    subprocess.Popen(
        cmd,
        creationflags=CREATE_NO_WINDOW,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
