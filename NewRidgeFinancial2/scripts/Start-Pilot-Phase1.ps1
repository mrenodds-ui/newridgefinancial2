# Phase 1 — Shadow mode (days 1–30)
# Records shadow start date; default pilot phase stays observe-only.

[CmdletBinding()]
param(
    [switch]$SkipValidation
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Nr2 = Join-Path $Root "NewRidgeFinancial2"

Write-Host "NR2 Phase 1 — Shadow Mode Setup" -ForegroundColor Cyan

$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
if (-not $py) {
    Write-Host "Python not found." -ForegroundColor Red
    exit 1
}

& $py.Source -c @"
import sys
from pathlib import Path
sys.path.insert(0, r'$Nr2')
from nr2_pilot import ensure_phase_started
print(ensure_phase_started('shadow'))
"@

if (-not $SkipValidation) {
    & $py.Source (Join-Path $Nr2 "scripts\validate_production_readiness.py")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host ""
Write-Host "Phase 1 (shadow) active:" -ForegroundColor Green
Write-Host "  - Compare NR2 to SoftDent daily"
Write-Host "  - ERA match review only; no bulk approve or export-approved"
Write-Host "  - Run validate_production_readiness.py weekly"
Write-Host ""
Write-Host "Start: StartProgram.bat -> https://127.0.0.1:8765/" -ForegroundColor Cyan
