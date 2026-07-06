@echo off
REM Background NR2 Workstation (popups only) — used by Startup folder.
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Workstation.ps1" -Hidden %*
set "EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %EXIT_CODE%
