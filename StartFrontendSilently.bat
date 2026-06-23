@echo off
setlocal

REM Frontend auto-launch is intentionally disabled in this workspace.
set "ROOT_DIR=%~dp0"
set "LOG_FILE=%ROOT_DIR%frontend-dev.log"

>> "%LOG_FILE%" echo [%date% %time%] Blocked frontend launch through StartFrontendSilently.bat because frontend auto-launch is disabled.
echo Frontend auto-launch is disabled for this workspace.
echo Run the SPA manually only when intentionally testing frontend behavior.
exit /b 1
