<#
.SYNOPSIS
  Run NR2 desktop UI validators before launch.
#>
[CmdletBinding()]
param(
    [string]$Nr2Dir
)

$ErrorActionPreference = 'Stop'
if (-not $Nr2Dir) {
    $Nr2Dir = Join-Path (Split-Path $PSScriptRoot -Parent) 'NewRidgeFinancial2'
}

$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    Write-Warning 'Node.js not found; skipping NR2 validators.'
    return
}

Push-Location $Nr2Dir
try {
    Write-Host 'Validating NR2 pages...' -ForegroundColor Cyan
    & node validate-pages.mjs
    if ($LASTEXITCODE -ne 0) { throw 'validate-pages.mjs failed' }

    Write-Host 'Validating HAL...' -ForegroundColor Cyan
    & node validate-hal.mjs
    if ($LASTEXITCODE -ne 0) { throw 'validate-hal.mjs failed' }

    Write-Host 'NR2 validators passed.' -ForegroundColor Green
} finally {
    Pop-Location
}
