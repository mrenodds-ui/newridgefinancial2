@echo off
REM Build NR2 Office Workstation zip installer for operatory PCs.
setlocal
set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%scripts\build-nr2-workstation-package.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" pause
endlocal & exit /b %EXIT_CODE%
