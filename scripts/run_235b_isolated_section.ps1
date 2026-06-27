<#
.SYNOPSIS
  Run one isolated 235B evaluation section (1-5) with lane isolation checks.

.DESCRIPTION
  Stops 14B chat/review lanes, starts only :11436, runs one section via run_235b_eval_section.py,
  stops 235B, and optionally restarts normal lanes with -RestartNormalLanes.

  Does not run multiple sections. Review the section report before running again.

.PARAMETER Section
  Section number 1 through 5.

.PARAMETER RestartNormalLanes
  After the section, start run_frontend_model.ps1 and run_backend_model.ps1 in new windows.

.PARAMETER OverwriteReport
  Allow overwriting an existing section report file.

.PARAMETER AllowDirtyRepo
  Allow tracked git changes (untracked 235b artifacts are ignored).

.PARAMETER ForceStopOllamaApp
  Pass through to stop_normal_model_lanes.ps1 when the tray app respawns :11434.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_235b_isolated_section.ps1 -Section 2
#>
[CmdletBinding(DefaultParameterSetName = 'Run')]
param(
    [Parameter(ParameterSetName = 'Help')]
    [switch]$Help,

    [Parameter(ParameterSetName = 'Run', Mandatory = $true)]
    [ValidateSet('1', '2', '3', '4', '5')]
    [string]$Section,

    [Parameter(ParameterSetName = 'Run')]
    [switch]$RestartNormalLanes,
    [Parameter(ParameterSetName = 'Run')]
    [switch]$OverwriteReport,
    [Parameter(ParameterSetName = 'Run')]
    [switch]$AllowDirtyRepo,
    [Parameter(ParameterSetName = 'Run')]
    [switch]$ForceStopOllamaApp
)

if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path -Full
    exit 0
}

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

$reportNames = @{
    '1' = '235b_section1_backend_pipeline_report.md'
    '2' = '235b_section2_frontend_dashboard_report.md'
    '3' = '235b_section3_ai_routing_report.md'
    '4' = '235b_section4_security_config_report.md'
    '5' = '235b_section5_tests_docs_report.md'
}
$reportPath = Join-Path $Root $reportNames[$Section]

Write-Host "=== 235B isolated section $Section workflow ===" -ForegroundColor Cyan

Write-Host "`n[1/10] Verify repo state"
git status --short
git log --oneline -8

if (-not $AllowDirtyRepo) {
    git diff --quiet
    if ($LASTEXITCODE -ne 0) {
        throw 'Tracked repo has unstaged changes. Commit or stash first, or pass -AllowDirtyRepo.'
    }
    git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        throw 'Tracked repo has staged changes. Commit or stash first, or pass -AllowDirtyRepo.'
    }
}

if ((Test-Path $reportPath) -and -not $OverwriteReport) {
    throw "Report already exists: $reportPath. Pass -OverwriteReport to replace it."
}

Write-Host "`n[2/10] Stop normal 14B lanes"
$stopScript = Join-Path $PSScriptRoot 'stop_normal_model_lanes.ps1'
if ($ForceStopOllamaApp) {
    & $stopScript -ForceStopOllamaApp
} else {
    & $stopScript
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[3/10] Verify :11434 and :11435 are down"
$code11434 = curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:11434/v1/models 2>$null
$code11435 = curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:11435/v1/models 2>$null
Write-Host ":11434 http=$code11434 :11435 http=$code11435"
if ($code11434 -match '^2' -or $code11435 -match '^2') {
    throw 'Normal lanes still respond. Do not start 235B until :11434 and :11435 are down.'
}

Write-Host "`n[4/10] Start evaluator lane :11436 only"
& (Join-Path $PSScriptRoot 'start_235b_evaluator_lane.ps1')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[5/10] Preflight qwen3:235b"
$env:OLLAMA_HOST = '127.0.0.1:11436'
ollama run qwen3:235b "Reply in one sentence: 235B evaluator is online."

Write-Host "`n[6/10] Run section $Section evaluation (one section only)"
$py = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }
$pyArgs = @((Join-Path $Root 'run_235b_eval_section.py'), $Section, '--isolated')
if ($OverwriteReport) { $pyArgs += '--overwrite' }
& $py @pyArgs
if ($LASTEXITCODE -ne 0) {
    if ($ForceStopOllamaApp) {
        & (Join-Path $PSScriptRoot 'stop_235b_evaluator_lane.ps1') -ForceStopOllamaApp
    } else {
        & (Join-Path $PSScriptRoot 'stop_235b_evaluator_lane.ps1')
    }
    exit $LASTEXITCODE
}

Write-Host "`n[7/10] Stop qwen3:235b and evaluator serve"
if ($ForceStopOllamaApp) {
    & (Join-Path $PSScriptRoot 'stop_235b_evaluator_lane.ps1') -ForceStopOllamaApp
} else {
    & (Join-Path $PSScriptRoot 'stop_235b_evaluator_lane.ps1')
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[8/10] Verify :11436 is down"
$code11436 = curl.exe -s -m 3 -o NUL -w "%{http_code}" http://127.0.0.1:11436/v1/models 2>$null
Write-Host ":11436 http=$code11436"
if ($code11436 -match '^2') {
    throw ':11436 still responds after teardown.'
}

if ($RestartNormalLanes) {
    Write-Host "`n[9/10] Restart normal lanes (foreground scripts in new windows)"
    Start-Process powershell -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'run_frontend_model.ps1') -WindowStyle Minimized
    Start-Process powershell -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'run_backend_model.ps1') -WindowStyle Minimized
    Start-Sleep -Seconds 5
    curl.exe -s http://127.0.0.1:11434/v1/models | Out-Null
    curl.exe -s http://127.0.0.1:11435/v1/models | Out-Null
    Write-Host 'Normal lanes restart requested. Keep those terminals open (foreground processes).'
}
else {
    Write-Host "`n[9/10] Skipping normal lane restart (pass -RestartNormalLanes to enable)"
}

Write-Host "`n[10/10] Final git status"
git status --short
Write-Host "`nDone. Report: $reportPath" -ForegroundColor Green
Write-Host 'Review the section report before approving the next section.' -ForegroundColor Green
