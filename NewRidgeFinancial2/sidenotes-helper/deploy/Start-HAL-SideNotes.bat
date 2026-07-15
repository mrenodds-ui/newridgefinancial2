@echo off
REM HAL SideNotes watcher launcher (workstation package).
REM Uses the same HAL neural voice as NR2 (Edge GuyNeural via 64-bit Python).
REM Local only; message body is never read.
setlocal
cd /d "%~dp0"

if not defined NEWRIDGE_FINANCIAL_REPO (
  if exist "C:\Users\mreno\newridgefamilyfinancial\NewRidgeFinancial2\hal_tts_cli.py" (
    set "NEWRIDGE_FINANCIAL_REPO=C:\Users\mreno\newridgefamilyfinancial"
  ) else if exist "C:\NewRidgeFamilyFinancial\NewRidgeFinancial2\hal_tts_cli.py" (
    set "NEWRIDGE_FINANCIAL_REPO=C:\NewRidgeFamilyFinancial"
  )
)
if not defined NR2_ROOT if defined NEWRIDGE_FINANCIAL_REPO (
  set "NR2_ROOT=%NEWRIDGE_FINANCIAL_REPO%\NewRidgeFinancial2"
)
if not defined NR2_NEURAL_PYTHON (
  if exist "%NEWRIDGE_FINANCIAL_REPO%\.venv\Scripts\python.exe" (
    set "NR2_NEURAL_PYTHON=%NEWRIDGE_FINANCIAL_REPO%\.venv\Scripts\python.exe"
  )
)

if not exist "py32\python.exe" (
  echo [ERROR] Bundled 32-bit Python not found at py32\python.exe
  echo This package looks incomplete. Re-copy the whole folder.
  pause
  exit /b 1
)
if not exist "config.json" (
  echo [ERROR] config.json not found. Run Install.bat ^(or Setup-Station.ps1^) first.
  pause
  exit /b 1
)
if not exist "neural_tts_bridge.py" (
  echo [WARN] neural_tts_bridge.py missing — voice will fall back to SAPI.
)
title HAL SideNotes Watcher
"py32\python.exe" "sidenotes_watcher.py"
echo.
echo Watcher stopped.
pause
