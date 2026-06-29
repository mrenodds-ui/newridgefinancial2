@echo off
REM HAL SideNotes watcher launcher (local only; runs the bundled 32-bit Python).
REM Double-click to start, or run from a terminal. Press Ctrl+C to stop.
setlocal
cd /d "%~dp0"
if not exist "py32\python.exe" (
  echo [ERROR] Bundled 32-bit Python not found at py32\python.exe
  echo See README.md for setup.
  pause
  exit /b 1
)
title HAL SideNotes Watcher
"py32\python.exe" "sidenotes_watcher.py"
echo.
echo Watcher stopped.
pause
