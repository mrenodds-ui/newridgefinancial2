@echo off
REM HAL SideNotes watcher launcher (workstation package).
REM Runs the bundled 32-bit Python. Local only; message body is never read.
setlocal
cd /d "%~dp0"
if not exist "py32\python.exe" (
  echo [ERROR] Bundled 32-bit Python not found at py32\python.exe
  echo This package looks incomplete. Re-copy the whole folder.
  pause
  exit /b 1
)
if not exist "config.json" (
  echo [ERROR] config.json not found. Run Install.bat ^(or Setup-Station.ps1^) first.
  pause
  exit /b 1
)
title HAL SideNotes Watcher
"py32\python.exe" "sidenotes_watcher.py"
echo.
echo Watcher stopped.
pause
