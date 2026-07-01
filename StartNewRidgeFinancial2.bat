@echo off
REM Alias — use StartProgram.bat (same desktop app).
setlocal
set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"
call "%ROOT_DIR%StartProgram.bat" %*
endlocal & exit /b %ERRORLEVEL%
