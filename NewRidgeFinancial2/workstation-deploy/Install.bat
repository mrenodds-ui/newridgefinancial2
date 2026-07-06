@echo off
REM NR2 Office Workstation - one-click installer (run once per operatory PC).
setlocal
cd /d "%~dp0"
echo.
echo NR2 Office Workstation Setup
echo ============================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup-Workstation.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%EXIT_CODE%"=="0" (
    echo Setup failed with exit code %EXIT_CODE%.
    pause
    exit /b %EXIT_CODE%
)
echo Setup complete.
pause
endlocal & exit /b 0
