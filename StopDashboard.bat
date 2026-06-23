@echo off
setlocal

REM Stop the frontend dashboard on port 5173, preferring the PM2-managed service when present.
set "ROOT_DIR=%~dp0"
set "LOG_FILE=%ROOT_DIR%frontend-dev.log"

cd /d "%ROOT_DIR%"

call pm2 describe new-ridge-frontend >NUL 2>&1
if not errorlevel 1 (
	echo Stopping PM2-managed frontend ^(new-ridge-frontend^) on port 5173...
	call pm2 stop new-ridge-frontend
	if errorlevel 1 (
		echo PM2 stop failed for new-ridge-frontend.
		exit /b 1
	)
	>> "%LOG_FILE%" echo [%date% %time%] Stopped PM2 frontend process new-ridge-frontend.
	echo Frontend stopped through PM2.
	exit /b 0
)

powershell -NoProfile -Command "$conn = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if ($null -ne $conn) { Write-Host ('Stopping frontend listener on port 5173 (PID {0})...' -f $conn.OwningProcess); Stop-Process -Id $conn.OwningProcess -Force; Add-Content -Path '%LOG_FILE%' -Value ('[{0}] Stopped frontend process on PID {1} through StopDashboard.' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $conn.OwningProcess) } else { Write-Host 'No frontend listener found on port 5173.' }"
if errorlevel 1 (
	echo Failed to stop the frontend listener on port 5173.
	exit /b 1
)

echo Frontend stop requested.