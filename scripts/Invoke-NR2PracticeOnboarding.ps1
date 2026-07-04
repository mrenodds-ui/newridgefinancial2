<#
.SYNOPSIS
  Verify NR2 practice paths, run readiness checks, and register optional scheduled tasks.

.DESCRIPTION
  One-shot onboarding for a practice workstation:
  - Ensures import inbox folders exist
  - Runs Verify-HAL-Readiness (optional import pull)
  - Runs NR2 validators
  - Registers the local accounting OCR scheduled task (optional)

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\Invoke-NR2PracticeOnboarding.ps1

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\scripts\Invoke-NR2PracticeOnboarding.ps1 -Pull -RegisterOcrTask
#>
[CmdletBinding()]
param(
    [switch]$Pull,
    [switch]$RegisterOcrTask,
    [int]$OcrRepeatMinutes = 30,
    [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}

$Nr2Dir = Join-Path $RepoRoot "NewRidgeFinancial2"
$SoftdentDir = Join-Path $RepoRoot "app_data\nr2\document_inbox\softdent"
$QuickbooksDir = Join-Path $RepoRoot "app_data\nr2\document_inbox\quickbooks"
$ProcessedDir = Join-Path $RepoRoot "app_data\nr2\document_inbox\processed"

function Write-Step([string]$Message) {
    Write-Host $Message -ForegroundColor Cyan
}

Write-Step "NR2 practice onboarding — repo: $RepoRoot"

@($SoftdentDir, $QuickbooksDir, $ProcessedDir) | ForEach-Object {
    New-Item -ItemType Directory -Force -Path $_ | Out-Null
    Write-Host "  OK  $_"
}

$readinessScript = Join-Path $Nr2Dir "import-automation\Verify-HAL-Readiness.ps1"
if (-not (Test-Path $readinessScript)) {
    throw "Missing Verify-HAL-Readiness.ps1 at $readinessScript"
}

Write-Step "Running HAL readiness verification..."
$readinessArgs = @()
if ($Pull) { $readinessArgs += "-Pull" }
& $readinessScript @readinessArgs
if ($LASTEXITCODE -ne 0) {
    throw "Verify-HAL-Readiness.ps1 failed (exit $LASTEXITCODE)"
}

$validatorsScript = Join-Path $PSScriptRoot "Invoke-NR2Validators.ps1"
if (Test-Path $validatorsScript) {
    Write-Step "Running NR2 validators..."
    & $validatorsScript -Nr2Dir $Nr2Dir
    if ($LASTEXITCODE -ne 0) {
        throw "Invoke-NR2Validators.ps1 failed (exit $LASTEXITCODE)"
    }
} else {
    Write-Warning "Invoke-NR2Validators.ps1 not found; skipping Node validators."
}

if ($RegisterOcrTask) {
    $ocrScript = Join-Path $PSScriptRoot "register_local_accounting_ocr_task.ps1"
    if (-not (Test-Path $ocrScript)) {
        throw "Missing register_local_accounting_ocr_task.ps1"
    }
    Write-Step "Registering local accounting OCR scheduled task (every $OcrRepeatMinutes min)..."
    & $ocrScript -RepeatMinutes $OcrRepeatMinutes
    if ($LASTEXITCODE -ne 0) {
        throw "register_local_accounting_ocr_task.ps1 failed (exit $LASTEXITCODE)"
    }
}

Write-Host ""
Write-Host "NR2 practice onboarding complete." -ForegroundColor Green
Write-Host "  SoftDent inbox:  $SoftdentDir"
Write-Host "  QuickBooks inbox: $QuickbooksDir"
Write-Host "  Next: launch Start Program and confirm Financial + Office Manager pages load."
