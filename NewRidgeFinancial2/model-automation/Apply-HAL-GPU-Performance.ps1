<#
.SYNOPSIS
  Apply Ollama GPU performance settings for single MoE on R9700 32 GB.

.DESCRIPTION
  Sets Ollama env for one loaded model on the discrete AMD GPU, creates
  hal-local:30b-a3b (qwen3:30b-a3b-instruct-2507-q4_K_M_K_M_K_M_K_M_K_M_K_M_K_M_K_M_K_M_K_M MoE), pins only that model, and verifies GPU load.
  OpenAI/cloud settings are not changed by this script.
#>
[CmdletBinding()]
param(
    [switch]$SkipEnv,
    [switch]$SkipPin
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$installScript = Join-Path $scriptRoot "Install-HAL-GPU-Single-MoE-30B-A3B.ps1"
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

function Get-R9700GpuIndex {
    $adapters = @(Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue)
    $amd = @($adapters | Where-Object {
        $_.Name -match "AMD|Radeon" -and $_.Name -notmatch "Intel"
    })
    if ($amd.Count -eq 0) {
        Write-Host "  WARNING: No AMD discrete adapter found via WMI; defaulting HIP_VISIBLE_DEVICES=0" -ForegroundColor DarkYellow
        return 0
    }
    $r9700 = $amd | Where-Object { $_.Name -match "R9700|AI PRO" } | Select-Object -First 1
    $chosen = if ($r9700) { $r9700 } else { $amd[0] }
    $index = [array]::IndexOf($amd, $chosen)
    if ($index -lt 0) { $index = 0 }
    Write-Host ("  Detected GPU: {0} → HIP/ROCm index {1}" -f $chosen.Name, $index) -ForegroundColor Green
    return $index
}

Write-Host "`n=== HAL GPU performance setup (single MoE 30B-A3B · R9700 32 GB) ===" -ForegroundColor Cyan

if (-not $SkipEnv) {
    Write-Host "`nUser environment (Ollama):" -ForegroundColor Yellow
    Set-UserEnv "OLLAMA_MODELS" $modelsPath
    if (Test-Path $tensilePath) {
        Set-UserEnv "ROCBLAS_TENSILE_LIBPATH" $tensilePath
    } else {
        Write-Host "  ROCBLAS_TENSILE_LIBPATH skipped (path not found)" -ForegroundColor DarkYellow
    }
    Set-UserEnv "OLLAMA_MAX_LOADED_MODELS" "1"
    Set-UserEnv "OLLAMA_NUM_PARALLEL" "1"
    Set-UserEnv "OLLAMA_IGPU_ENABLE" "0"
    Set-UserEnv "OLLAMA_HOST" "127.0.0.1:11434"
    $gpuIndex = Get-R9700GpuIndex
    Set-UserEnv "HIP_VISIBLE_DEVICES" "$gpuIndex"
    Set-UserEnv "ROCR_VISIBLE_DEVICES" "$gpuIndex"
}

if (-not $SkipPin) {
    Write-Host "`nPinning single GPU MoE (hal-local:30b-a3b qwen3:30b-a3b-instruct-2507-q4_K_M_K_M_K_M_K_M_K_M_K_M_K_M_K_M_K_M_K_M)..." -ForegroundColor Yellow
    & $installScript
    if ($LASTEXITCODE -ne 0) { throw "Install-HAL-GPU-Single-MoE-30B-A3B failed" }

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
Write-Host "Rollback to dense 32B: .\Install-HAL-GPU-Single-32B.ps1 then restore gateway/inventory if needed." -ForegroundColor DarkGray
Write-Host "Re-open NR2 if the program is already running." -ForegroundColor Green
