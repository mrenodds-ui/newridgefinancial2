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
    [ValidateSet('1', '2', '3', '4', '5', '1a', '1b', '1c', '2a', '2b', '2c', '1a1', '1a2', '1b1', '1b2', '1c1', '1c2', '2a1', '2a2', '2b1', '2b2', '2c1', '2c2')]
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
    '1a' = '235b_section1a_softdent_period_report.md'
    '1b' = '235b_section1b_import_loader_report.md'
    '1c' = '235b_section1c_import_pipeline_report.md'
    '2a' = '235b_section2a_widget_contract_report.md'
    '2b' = '235b_section2b_financial_overview_report.md'
    '2c' = '235b_section2c_page_canvas_report.md'
    '1a1' = '235b_section1a1_softdent_sync_core_report.md'
    '1a2' = '235b_section1a2_direct_pipeline_report.md'
    '1b1' = '235b_section1b1_import_loader_periods_report.md'
    '1b2' = '235b_section1b2_import_loader_tests_report.md'
    '1c1' = '235b_section1c1_import_loader_py_report.md'
    '1c2' = '235b_section1c2_import_sync_report.md'
    '2a1' = '235b_section2a1_hal_skills_report.md'
    '2a2' = '235b_section2a2_widget_contract_report.md'
    '2b1' = '235b_section2b1_master_chart_report.md'
    '2b2' = '235b_section2b2_financial_dashboard_report.md'
    '2c1' = '235b_section2c1_page_canvas_report.md'
    '2c2' = '235b_section2c2_hal_page_validate_report.md'
}
$reportPath = Join-Path $Root $reportNames[$Section]

Write-Host "=== 235B isolated section $Section workflow ===" -ForegroundColor Cyan

Write-Host "`n[1/10] Build NR2 micro focus bundles (if script present)"
$focusScript = Join-Path $PSScriptRoot 'build_235b_nr2_focus.ps1'
if (Test-Path $focusScript) {
    & $focusScript
    if (-not $?) {
        throw 'Focus bundle build failed.'
    }
}

Write-Host "`n[2/10] Verify repo state"
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

Write-Host "`n[3/10] Stop normal 14B lanes"
$stopScript = Join-Path $PSScriptRoot 'stop_normal_model_lanes.ps1'
if ($ForceStopOllamaApp) {
    & $stopScript -ForceStopOllamaApp
} else {
    & $stopScript
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[4/10] Verify :11434 and :11435 are down"
$code11434 = curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:11434/v1/models 2>$null
$code11435 = curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:11435/v1/models 2>$null
Write-Host ":11434 http=$code11434 :11435 http=$code11435"
if ($code11434 -match '^2' -or $code11435 -match '^2') {
    throw 'Normal lanes still respond. Do not start 235B until :11434 and :11435 are down.'
}

Write-Host "`n[5/10] Start evaluator lane :11436 only"
& (Join-Path $PSScriptRoot 'start_235b_evaluator_lane.ps1')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[6/10] Preflight qwen3:235b on :11436"
$modelsJson = curl.exe -s -m 30 http://127.0.0.1:11436/v1/models
if ($modelsJson -notmatch 'qwen3:235b') {
    throw 'qwen3:235b not listed on evaluator lane :11436.'
}
Write-Host '235B preflight OK.'

Write-Host "`n[7/10] Run section $Section evaluation (one section only)"
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

Write-Host "`n[8/10] Stop qwen3:235b and evaluator serve"
if ($ForceStopOllamaApp) {
    & (Join-Path $PSScriptRoot 'stop_235b_evaluator_lane.ps1') -ForceStopOllamaApp
} else {
    & (Join-Path $PSScriptRoot 'stop_235b_evaluator_lane.ps1')
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`n[9/10] Verify :11436 is down"
$code11436 = curl.exe -s -m 3 -o NUL -w "%{http_code}" http://127.0.0.1:11436/v1/models 2>$null
Write-Host ":11436 http=$code11436"
if ($code11436 -match '^2') {
    throw ':11436 still responds after teardown.'
}

if ($RestartNormalLanes) {
    Write-Host "`n[10/10] Restart normal lanes (foreground scripts in new windows)"
    Start-Process powershell -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'run_frontend_model.ps1') -WindowStyle Minimized
    Start-Process powershell -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'run_backend_model.ps1') -WindowStyle Minimized
    Start-Sleep -Seconds 5
    curl.exe -s http://127.0.0.1:11434/v1/models | Out-Null
    curl.exe -s http://127.0.0.1:11435/v1/models | Out-Null
    Write-Host 'Normal lanes restart requested. Keep those terminals open (foreground processes).'
}
else {
    Write-Host "`n[10/10] Skipping normal lane restart (pass -RestartNormalLanes to enable)"
}

Write-Host "`n[11/11] Final git status"
git status --short
Write-Host "`nDone. Report: $reportPath" -ForegroundColor Green
Write-Host 'Review the section report before approving the next section.' -ForegroundColor Green
