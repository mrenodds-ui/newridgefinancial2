@echo off
setlocal

REM Stop NewRidgeFinancial 2.0 and any stale legacy listeners.
set "ROOT_DIR=%~dp0"
set "LOG_FILE=%ROOT_DIR%stop-program.log"

cd /d "%ROOT_DIR%"

powershell -NoProfile -Command "$ports = 8765,5173,5174,5175,5176,8095,8096; $stopped = $false; foreach ($port in $ports) { $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue; foreach ($conn in $conns) { $stopped = $true; Write-Host ('Stopping listener on port {0} (PID {1})...' -f $port, $conn.OwningProcess); Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue; Add-Content -Path '%LOG_FILE%' -Value ('[{0}] Stopped process on port {1}, PID {2}.' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $port, $conn.OwningProcess) } }; if (-not $stopped) { Write-Host 'No program listeners found on ports 8765, 5173-5176, 8095, or 8096.' }"
if errorlevel 1 (
    echo Failed to stop program listeners.
    exit /b 1
)

echo Program stop requested.
