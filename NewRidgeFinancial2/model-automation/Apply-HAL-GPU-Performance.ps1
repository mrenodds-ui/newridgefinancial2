<#
.SYNOPSIS
  Apply Ollama GPU performance settings for R9700 32 GB HAL workstation.

.DESCRIPTION
  Sets recommended user-level Ollama environment variables, creates hal-escalate:30b
  (capped 4096 ctx), pins hal-chat:8b + hal-escalate:30b, and verifies GPU load.
#>
[CmdletBinding()]
param(
    [switch]$SkipEnv,
    [switch]$SkipPin
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$installScript = Join-Path $scriptRoot "Install-HAL-GPU-Chat-Escalate-Lanes.ps1"
$registerScript = Join-Path $scriptRoot "Register-HAL-Model-Automation.ps1"

$ollamaRoot = "$env:LOCALAPPDATA\Programs\Ollama"
$tensilePath = Join-Path $ollamaRoot "lib\ollama\rocm_v7_1\rocblas\library"
$modelsPath = "D:\LocalAI\ActiveModels"

function Set-UserEnv {
    param([string]$Name, [string]$Value)
    $current = [Environment]::GetEnvironmentVariable($Name, "User")
    if ($current -eq $Value) {
        Write-Host "  $Name already set" -ForegroundColor DarkGray
        return
    }
    [Environment]::SetEnvironmentVariable($Name, $Value, "User")
    Set-Item -Path "Env:$Name" -Value $Value
    Write-Host "  $Name = $Value" -ForegroundColor Green
}

Write-Host "`n=== HAL GPU performance setup (R9700 32 GB) ===" -ForegroundColor Cyan

if (-not $SkipEnv) {
    Write-Host "`nUser environment (Ollama):" -ForegroundColor Yellow
    Set-UserEnv "OLLAMA_MODELS" $modelsPath
    if (Test-Path $tensilePath) {
        Set-UserEnv "ROCBLAS_TENSILE_LIBPATH" $tensilePath
    } else {
        Write-Host "  ROCBLAS_TENSILE_LIBPATH skipped (path not found)" -ForegroundColor DarkYellow
    }
    # Keep exactly two GPU lanes resident; avoid loading a third model that evicts pins.
    Set-UserEnv "OLLAMA_MAX_LOADED_MODELS" "2"
    # One request at a time — safer VRAM on dual-resident 8B+30B layout.
    Set-UserEnv "OLLAMA_NUM_PARALLEL" "1"
    # Do not route work to Intel iGPU.
    Set-UserEnv "OLLAMA_IGPU_ENABLE" "0"
}

if (-not $SkipPin) {
    Write-Host "`nPinning GPU models (8B chat + 30B escalation, capped ctx)..." -ForegroundColor Yellow
    & $installScript
    if ($LASTEXITCODE -ne 0) { throw "Install-HAL-GPU-Chat-Escalate-Lanes failed" }

    Write-Host "`nRegistering warmup automation..." -ForegroundColor Yellow
    & $registerScript
    if ($LASTEXITCODE -ne 0) { throw "Register-HAL-Model-Automation failed" }
}

Write-Host "`nVerification:" -ForegroundColor Yellow
$ollama = if (Test-Path "$ollamaRoot\ollama.exe") { "$ollamaRoot\ollama.exe" } else { "ollama" }
& $ollama ps

$active = powercfg /GETACTIVESCHEME 2>$null
if ($active -match "High performance|8c5e7fda") {
    Write-Host "Power plan: High performance" -ForegroundColor Green
} else {
    Write-Host "Tip: set power plan to High performance: powercfg /SETACTIVE 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c" -ForegroundColor DarkYellow
}

Write-Host "`nDone. Restart Ollama app if env vars were new (or log off/on)." -ForegroundColor Green
Write-Host "Re-open NR2 if the program is already running." -ForegroundColor Green
