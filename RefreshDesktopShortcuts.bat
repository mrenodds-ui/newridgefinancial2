@echo off
REM Refresh Start Program desktop shortcuts for NewRidgeFinancial 2.0.
setlocal
set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%scripts\Refresh-NR2-DesktopShortcut.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Refresh desktop shortcuts failed with exit code %EXIT_CODE%.
    pause
)

endlocal & exit /b %EXIT_CODE%
