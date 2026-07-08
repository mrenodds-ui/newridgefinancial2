@echo off
REM HAL SideNotes watcher launcher (local only; runs the bundled 32-bit Python).
REM Only ONE watcher should run — NR2 Workstation starts it automatically.
setlocal
cd /d "%~dp0"
if not exist "py32\python.exe" (
  echo [ERROR] Bundled 32-bit Python not found at py32\python.exe
  echo See README.md for setup.
  pause
  exit /b 1
)
if exist "sidenotes-watcher.pid" (
  for /f "usebackq delims=" %%P in ("sidenotes-watcher.pid") do (
    tasklist /FI "PID eq %%P" 2>nul | find "python.exe" >nul
    if not errorlevel 1 (
      echo SideNotes watcher is already running ^(PID %%P^).
      echo Close NR2 Workstation or stop that process before starting another copy.
      pause
      exit /b 0
    )
  )
)
title HAL SideNotes Watcher
"py32\python.exe" "sidenotes_watcher.py"
echo.
echo Watcher stopped.
pause
