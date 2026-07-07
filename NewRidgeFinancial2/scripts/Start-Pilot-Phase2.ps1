# Phase 2 — Supervised pilot (days 31–60)
# Registers import automation and validates supervised-pilot readiness.

[CmdletBinding()]
param(
    [switch]$SkipImportTask,
    [switch]$SkipValidation
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Nr2 = Join-Path $Root "NewRidgeFinancial2"

Write-Host "NR2 Phase 2 — Supervised Pilot Setup" -ForegroundColor Cyan

if (-not $SkipImportTask) {
    $reg = Join-Path $Nr2 "import-automation\Register-HAL-Import-Automation.ps1"
    if (Test-Path $reg) {
        & $reg
        $env:NR2_IMPORT_TASK_REGISTERED = "1"
        Write-Host "Import sync scheduled task registered." -ForegroundColor Green
    } else {
        Write-Host "Import automation script not found: $reg" -ForegroundColor Yellow
    }
    $docReg = Join-Path $Nr2 "import-automation\Register-HAL-Document-Source-Automation.ps1"
    if (Test-Path $docReg) {
        & $docReg
        Write-Host "Document source sync scheduled task registered." -ForegroundColor Green
    }
}

$roleExample = Join-Path $Nr2 "docs\examples\workstation_role.json.example"
$roleLive = Join-Path $Root "app_data\nr2\workstation_role.json"
if ((Test-Path $roleExample) -and -not (Test-Path $roleLive)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $roleLive) | Out-Null
    Copy-Item $roleExample $roleLive
    Write-Host "Created workstation role: $roleLive (office_manager)" -ForegroundColor Green
}

if (-not $SkipValidation) {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
    if ($py) {
        & $py.Source -c @"
import sys
sys.path.insert(0, r'$Nr2')
from nr2_pilot import ensure_phase_started
print(ensure_phase_started('supervised'))
"@
        & $py.Source (Join-Path $Nr2 "scripts\validate_supervised_pilot.py")
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}

Write-Host ""
Write-Host "Phase 2 enabled:" -ForegroundColor Green
Write-Host "  - Morning routine + alert toasts (server scheduler)"
Write-Host "  - ERA match review with human sign-off on every match"
Write-Host "  - Posting queue on encrypted DB (supervised approvals only)"
Write-Host "  - Optional: set NR2_QBO_CLIENT_ID for QB read-only sync"
Write-Host ""
Write-Host "Start: StartProgram.bat -> https://127.0.0.1:8765/" -ForegroundColor Cyan
