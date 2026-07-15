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

$indexPath = Join-Path $Nr2Dir 'site\index.html'
$isApex = $false
$isOpticalClean = $false
if (Test-Path $indexPath) {
    $indexHead = (Get-Content -Path $indexPath -TotalCount 40 -ErrorAction SilentlyContinue) -join "`n"
    $isApex = $indexHead -match 'nr2-apex|apex-bridge'
    $isOpticalClean = $indexHead -match 'nr2-boot\.js|nr2-optical-beam-touch|nr2-11000-clean|nr2-12016'
}
$buildPath = Join-Path $Nr2Dir 'nr2-build.json'
if (Test-Path $buildPath) {
    $buildRaw = Get-Content $buildPath -Raw -ErrorAction SilentlyContinue
    if ($buildRaw -match 'nr2-clean|nr2-11000-clean|nr2-12016|honest-subpages') { $isOpticalClean = $true }
}

Push-Location $Nr2Dir
try {
    if ($isApex) {
        Write-Host 'Validating Apex Bridge...' -ForegroundColor Cyan
        & node validate-apex.mjs
        if ($LASTEXITCODE -ne 0) { throw 'validate-apex.mjs failed' }
    } elseif ($isOpticalClean) {
        Write-Host 'Validating NR2 optical clean entry...' -ForegroundColor Cyan
        & node validate-pages.mjs
        if ($LASTEXITCODE -ne 0) { throw 'validate-pages.mjs failed' }
        Write-Host 'Skipping legacy validate-hal.mjs (optical cutover).' -ForegroundColor DarkYellow
    } else {
        Write-Host 'Validating NR2 pages...' -ForegroundColor Cyan
        & node validate-pages.mjs
        if ($LASTEXITCODE -ne 0) { throw 'validate-pages.mjs failed' }

        Write-Host 'Validating HAL...' -ForegroundColor Cyan
        & node validate-hal.mjs
        if ($LASTEXITCODE -ne 0) { throw 'validate-hal.mjs failed' }
    }

    Write-Host 'NR2 validators passed.' -ForegroundColor Green
} finally {
    Pop-Location
}
