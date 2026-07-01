@echo off
REM Stop Program — close NewRidgeFinancial 2.0 desktop app.
setlocal
set "ROOT_DIR=%~dp0"
call "%ROOT_DIR%StopNewRidgeFinancial2.bat"
endlocal & exit /b %ERRORLEVEL%
