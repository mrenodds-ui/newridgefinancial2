@echo off
REM HAL SideNotes - one-click workstation installer.
REM Launches the guided PowerShell setup (station name + shared folder + shortcuts).
setlocal
cd /d "%~dp0"
echo Starting HAL SideNotes workstation setup...
powershell -NoProfile -ExecutionPolicy Bypass -File "Setup-Station.ps1"
echo.
pause
