@echo off
REM NewRidgeFinancial 2.0 desktop app (single window, no browser).
setlocal
set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%scripts\start_nr2_1966.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Start failed with exit code %EXIT_CODE%.
    pause
)

endlocal & exit /b %EXIT_CODE%
