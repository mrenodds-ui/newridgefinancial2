# Phase 3 — Production cutover (days 61+)
# Requires supervised pilot checks, attestation, and minimum shadow/supervised duration.

[CmdletBinding()]
param(
    [string]$SignedBy = "",
    [string]$AttestationNote = "Office manager attests NR2 import accuracy vs SoftDent for pilot period.",
    [switch]$SkipValidation,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Nr2 = Join-Path $Root "NewRidgeFinancial2"
$AttestationPath = Join-Path $Root "app_data\nr2\pilot_cutover.json"

Write-Host "NR2 Phase 3 — Production Cutover Setup" -ForegroundColor Cyan

$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
if (-not $py) {
    Write-Host "Python not found." -ForegroundColor Red
    exit 1
}

if (-not $SkipValidation) {
    & $py.Source (Join-Path $Nr2 "scripts\validate_supervised_pilot.py")
    if ($LASTEXITCODE -ne 0 -and -not $Force) { exit $LASTEXITCODE }
}

if (-not $SignedBy) {
    $SignedBy = Read-Host "Office manager / dentist name for cutover attestation"
}
if (-not $SignedBy) {
    Write-Host "SignedBy is required." -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path (Split-Path $AttestationPath) | Out-Null
$attestation = @{
    signed_by = $SignedBy.Trim()
    signed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    note = $AttestationNote
    softdent_parallel_complete = $true
} | ConvertTo-Json -Depth 4
Set-Content -Path $AttestationPath -Value $attestation -Encoding UTF8
Write-Host "Wrote attestation: $AttestationPath" -ForegroundColor Green

& $py.Source -c @"
import sys
from pathlib import Path
sys.path.insert(0, r'$Nr2')
from nr2_pilot import ensure_phase_started
print(ensure_phase_started('cutover'))
"@

$env:NR2_PILOT_PHASE = "cutover"

if (-not $SkipValidation) {
    & $py.Source (Join-Path $Nr2 "scripts\validate_cutover_readiness.py")
    if ($LASTEXITCODE -ne 0 -and -not $Force) { exit $LASTEXITCODE }
}

Write-Host ""
Write-Host "Phase 3 cutover enabled on this workstation:" -ForegroundColor Green
Write-Host "  - NR2 may operate as system of record"
Write-Host "  - Approved posting export unlocked"
Write-Host "  - Keep backups and nr2_financial_mutations.log reviews"
Write-Host ""
Write-Host "Persist phase for new shells: setx NR2_PILOT_PHASE cutover" -ForegroundColor Yellow
Write-Host "Start: StartProgram.bat -> https://127.0.0.1:8765/" -ForegroundColor Cyan
