@echo off
REM Start Program — NewRidgeFinancial 2.0 desktop app (single pywebview window).
setlocal
set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%scripts\start_program.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Start Program failed with exit code %EXIT_CODE%.
    pause
)

endlocal & exit /b %EXIT_CODE%
