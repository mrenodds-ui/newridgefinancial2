@echo off
setlocal
cd /d "%~dp0\.."
echo Running Moonshot HAL page recommendations consult (local)...
echo Repo: %CD%
where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: python not on PATH
  exit /b 1
)
python scripts\run_moonshot_hal_page_recommendations_consult.py
set ERR=%ERRORLEVEL%
echo.
if exist "NewRidgeFinancial2\docs\MOONSHOT_HAL_PAGE_RECOMMENDATIONS_CONSULT_*.md" (
  echo Report written under NewRidgeFinancial2\docs\
  dir /b /o-d "NewRidgeFinancial2\docs\MOONSHOT_HAL_PAGE_RECOMMENDATIONS_CONSULT_*.md"
)
exit /b %ERR%
