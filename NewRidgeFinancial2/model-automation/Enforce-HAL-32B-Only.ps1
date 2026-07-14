<#
.SYNOPSIS
  Keep only hal-local:32b (+ base qwen3:32b) on disk and pin it on the R9700 GPU.

.DESCRIPTION
  Evicts non-32B residents, removes other Ollama tags, re-applies single-model
  GPU env, and pins hal-local:32b with keep_alive=-1.
#>
[CmdletBinding()]
param(
    [switch]$SkipDelete,
    [string]$OllamaExe = "C:\Users\mreno\AppData\Local\Programs\Ollama\ollama.exe"
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$applyScript = Join-Path $scriptRoot "Apply-HAL-GPU-Performance.ps1"
$ollama = if (Test-Path $OllamaExe) { $OllamaExe } else { "ollama" }

$keep = @{
    "hal-local:32b" = $true
    "qwen3:32b" = $true
}

Write-Host ""
Write-Host "=== Enforce HAL 32B-only (GPU + disk) ===" -ForegroundColor Cyan

try {
    $ps = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/ps" -TimeoutSec 10
    foreach ($m in @($ps.models)) {
        $name = [string]($m.name)
        if ($name -and -not $keep.ContainsKey($name)) {
            $body = @{ model = $name; keep_alive = 0 } | ConvertTo-Json -Compress
            try {
                Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/generate" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 120 | Out-Null
                Write-Host "Evicted loaded model: $name" -ForegroundColor Yellow
            } catch {
                Write-Host "Could not evict $name (may already be gone)" -ForegroundColor DarkGray
            }
        }
    }
} catch {
    Write-Host "Ollama /api/ps not reachable yet - continuing." -ForegroundColor DarkYellow
}

if (-not $SkipDelete) {
    Write-Host ""
    Write-Host "Removing non-approved Ollama tags..." -ForegroundColor Yellow
    $listed = & $ollama list 2>$null
    foreach ($line in $listed) {
        if ($line -match "^\s*NAME\b") { continue }
        $tag = ($line -split "\s+")[0]
        if (-not $tag -or $tag -eq "NAME") { continue }
        if ($keep.ContainsKey($tag)) {
            Write-Host "  keep $tag" -ForegroundColor DarkGray
            continue
        }
        Write-Host "  ollama rm $tag" -ForegroundColor Yellow
        & $ollama rm $tag
    }
}

Write-Host ""
Write-Host "Applying single-32B GPU pin..." -ForegroundColor Yellow
& $applyScript
if ($LASTEXITCODE -ne 0) { throw "Apply-HAL-GPU-Performance failed" }

Write-Host ""
Write-Host "Loaded:" -ForegroundColor Green
& $ollama ps
Write-Host ""
Write-Host "Installed:" -ForegroundColor Green
& $ollama list
