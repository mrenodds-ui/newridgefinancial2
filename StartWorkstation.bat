@echo off
REM Start Workstation - NR2 Office Workstation (Send Message + Ask HAL only).
setlocal
set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%scripts\start_workstation.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Start Workstation failed with exit code %EXIT_CODE%.
    pause
)

endlocal & exit /b %EXIT_CODE%
