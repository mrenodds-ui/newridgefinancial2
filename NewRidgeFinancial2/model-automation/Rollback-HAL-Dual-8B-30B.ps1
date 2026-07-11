<#
.SYNOPSIS
  Restore the prior dual-pin HAL layout (hal-chat:8b + hal-escalate:30b).

.DESCRIPTION
  Reverts OLLAMA_MAX_LOADED_MODELS to 2, restores prior Apply-HAL-GPU-Performance
  dual-pin install, and unpins hal-local:24b. Does not delete the 24B model files.
#>
[CmdletBinding()]
param(
    [string]$OllamaHost = "http://127.0.0.1:11434",
    [switch]$SkipEnv
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$dualInstall = Join-Path $scriptRoot "Install-HAL-GPU-Chat-Escalate-Lanes.ps1"
$registerScript = Join-Path $scriptRoot "Register-HAL-Model-Automation.ps1"
$snapshotPath = Join-Path $scriptRoot "rollback-snapshots\pre-single-24b-env.json"

function Set-UserEnv {
    param([string]$Name, [string]$Value)
    [Environment]::SetEnvironmentVariable($Name, $Value, "User")
    Set-Item -Path "Env:$Name" -Value $Value
    Write-Host "  $Name = $Value" -ForegroundColor Green
}

Write-Host "`n=== HAL rollback: dual 8B+30B pin ===" -ForegroundColor Cyan

if (-not $SkipEnv) {
    Write-Host "`nRestoring dual-pin Ollama env:" -ForegroundColor Yellow
    Set-UserEnv "OLLAMA_MAX_LOADED_MODELS" "2"
    Set-UserEnv "OLLAMA_NUM_PARALLEL" "1"
    Set-UserEnv "OLLAMA_IGPU_ENABLE" "0"
    # Keep loopback binding after rollback (safer than prior 0.0.0.0).
    Set-UserEnv "OLLAMA_HOST" "127.0.0.1:11434"
    if (Test-Path $snapshotPath) {
        Write-Host "  Snapshot available: $snapshotPath" -ForegroundColor DarkGray
    }
}

$body = @{ model = "hal-local:24b"; keep_alive = 0 } | ConvertTo-Json -Compress
try {
    Invoke-RestMethod -Uri "$OllamaHost/api/generate" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 120 | Out-Null
    Write-Host "Unpinned hal-local:24b" -ForegroundColor DarkGray
} catch {
    Write-Host "hal-local:24b not loaded" -ForegroundColor DarkGray
}

Write-Host "`nReinstalling dual GPU lanes..." -ForegroundColor Yellow
& $dualInstall
if ($LASTEXITCODE -ne 0) { throw "Install-HAL-GPU-Chat-Escalate-Lanes failed" }

& $registerScript
if ($LASTEXITCODE -ne 0) { throw "Register-HAL-Model-Automation failed" }

Write-Host "`nRollback complete. Restore site/data/hal-models.json from git if config was committed:" -ForegroundColor Green
Write-Host "  git checkout -- NewRidgeFinancial2/site/data/hal-models.json NewRidgeFinancial2/nr2_hal_gateway.py"
Write-Host "Restart Ollama if env vars changed, then re-open NR2." -ForegroundColor Green
