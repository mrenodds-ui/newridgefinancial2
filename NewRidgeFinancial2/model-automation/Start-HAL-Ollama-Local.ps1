<#
.SYNOPSIS
  Start Ollama bound to 127.0.0.1 only with single-24B GPU env.

.DESCRIPTION
  Stops the Ollama tray app / serve processes and starts `ollama serve` with
  loopback host, MAX_LOADED_MODELS=1, and R9700 visibility. Then pins hal-local:24b.
#>
[CmdletBinding()]
param(
    [switch]$SkipPin
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ollama = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
if (-not (Test-Path $ollama)) { throw "ollama.exe not found" }

Write-Host "Stopping existing Ollama processes..." -ForegroundColor Yellow
Get-Process "ollama","ollama app" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

$envMap = @{
    OLLAMA_HOST              = "127.0.0.1:11434"
    OLLAMA_MAX_LOADED_MODELS = "1"
    OLLAMA_NUM_PARALLEL      = "1"
    OLLAMA_IGPU_ENABLE       = "0"
    HIP_VISIBLE_DEVICES      = "0"
    ROCR_VISIBLE_DEVICES     = "0"
    OLLAMA_MODELS           = "D:\LocalAI\ActiveModels"
}
$tensile = "$env:LOCALAPPDATA\Programs\Ollama\lib\ollama\rocm_v7_1\rocblas\library"
if (Test-Path $tensile) { $envMap["ROCBLAS_TENSILE_LIBPATH"] = $tensile }

foreach ($k in $envMap.Keys) {
    [Environment]::SetEnvironmentVariable($k, $envMap[$k], "User")
    Set-Item -Path "Env:$k" -Value $envMap[$k]
}

Write-Host "Starting ollama serve on 127.0.0.1:11434 ..." -ForegroundColor Cyan
Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden -Environment $envMap | Out-Null

for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 1
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/version" -TimeoutSec 2 | Out-Null
        break
    } catch { }
}

$listen = netstat -ano | Select-String ":11434"
Write-Host $listen
if ($listen -match "0\.0\.0\.0:11434") {
    throw "Ollama is still listening on 0.0.0.0 — tray app may have respawned. Close Ollama from the system tray and re-run."
}

if (-not $SkipPin) {
    & (Join-Path $scriptRoot "Keep-HAL-Models-Warm.ps1") -Models @("hal-local:24b")
    & $ollama ps
}

Write-Host "Done. Prefer this script over the Ollama tray app so LAN binding stays off." -ForegroundColor Green
