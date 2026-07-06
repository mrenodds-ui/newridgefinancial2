@echo off
REM Create or refresh NR2 Office Workstation desktop shortcut.
setlocal
set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%scripts\Refresh-NR2-WorkstationShortcut.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Refresh workstation shortcut failed with exit code %EXIT_CODE%.
    pause
)

endlocal & exit /b %EXIT_CODE%
