@echo off
setlocal

cd /d "%~dp0"
if "%HAL_EVAL_USERNAME%"=="" set "HAL_EVAL_USERNAME=admin"
if "%HAL_EVAL_PASSWORD%"=="" set "HAL_EVAL_PASSWORD=change-me"
set "RUN_ID=%RANDOM%%RANDOM%"
set "LOG_FILE=%~dp0hal-audit-task-%RUN_ID%.log"

echo LOG_FILE:%LOG_FILE%

call .\node_modules\.bin\playwright.cmd test --config="%~dp0playwright.config.ts" src/e2e/hal-random-audit.spec.ts --project=chromium --reporter=line > "%LOG_FILE%" 2>&1
echo EXIT:%ERRORLEVEL%>> "%LOG_FILE%"
exit /b %ERRORLEVEL%