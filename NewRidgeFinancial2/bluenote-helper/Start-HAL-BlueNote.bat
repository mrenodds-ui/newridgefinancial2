@echo off
REM Prefer NR2 repo BlueNote helper so workstation bridge can supervise the same PID.
setlocal
if not defined NEWRIDGE_FINANCIAL_REPO set "NEWRIDGE_FINANCIAL_REPO=C:\Users\mreno\newridgefamilyfinancial"
if not exist "%NEWRIDGE_FINANCIAL_REPO%\NewRidgeFinancial2\bluenote-helper\bluenote_watcher.py" (
  if exist "C:\NewRidgeFamilyFinancial\NewRidgeFinancial2\bluenote-helper\bluenote_watcher.py" (
    set "NEWRIDGE_FINANCIAL_REPO=C:\NewRidgeFamilyFinancial"
  )
)
set "NR2_ROOT=%NEWRIDGE_FINANCIAL_REPO%\NewRidgeFinancial2"
if not defined NR2_NEURAL_PYTHON (
  if exist "%NEWRIDGE_FINANCIAL_REPO%\.venv\Scripts\python.exe" (
    set "NR2_NEURAL_PYTHON=%NEWRIDGE_FINANCIAL_REPO%\.venv\Scripts\python.exe"
  ) else (
    set "NR2_NEURAL_PYTHON=python"
  )
)
if not defined NR2_SIDENOTES_HUB_DATA set "NR2_SIDENOTES_HUB_DATA=C:\softdent\HAL-BlueNote-Workstation\data"
if not defined NR2_BLUENOTE_HUB_DATA set "NR2_BLUENOTE_HUB_DATA=%NR2_SIDENOTES_HUB_DATA%"
set "PYTHONUNBUFFERED=1"
cd /d "%NR2_ROOT%\bluenote-helper"
title HAL BlueNote Watcher
"%NR2_NEURAL_PYTHON%" -u bluenote_watcher.py
echo.
echo Watcher stopped.
pause
