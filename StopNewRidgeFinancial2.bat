@echo off
setlocal
set "ROOT_DIR=%~dp0"

powershell -NoProfile -Command "$pidFile = Join-Path '%ROOT_DIR%' 'app_data\nr2\nr2-desktop.pid'; if (Test-Path $pidFile) { $appPid = [int](Get-Content $pidFile -Raw); if (Get-Process -Id $appPid -ErrorAction SilentlyContinue) { Write-Host ('Stopping NewRidgeFinancial 2.0 desktop app (PID {0})...' -f $appPid); Stop-Process -Id $appPid -Force -ErrorAction SilentlyContinue } else { Write-Host 'Recorded desktop app process is not running.' }; Remove-Item $pidFile -Force -ErrorAction SilentlyContinue } else { Write-Host 'No NewRidgeFinancial 2.0 desktop PID file found.' }"
