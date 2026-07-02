<#
.SYNOPSIS
  Run NR2 micro 235B sections with one evaluator lane session (faster than per-section teardown).
#>
[CmdletBinding()]
param(
    [ValidateSet('1a', '1b', '1c', '2a', '2b', '2c')]
    [string[]]$Sections = @('1a', '1b', '1c', '2a', '2b', '2c')
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
$logDir = Join-Path $Root '.local_logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$batchLog = Join-Path $logDir '235b_nr2_micro_eval.log'

function Log([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -Path $batchLog -Value $line
    Write-Host $line
}

Log "Sections: $($Sections -join ', ')"

& (Join-Path $PSScriptRoot 'build_235b_nr2_focus.ps1') | Out-Null

Log 'Stopping all Ollama lanes'
Stop-Process -Name 'ollama app' -Force -ErrorAction SilentlyContinue
Get-Process ollama -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
& (Join-Path $PSScriptRoot 'stop_normal_model_lanes.ps1') -ForceStopOllamaApp
if ($LASTEXITCODE -ne 0) { throw 'stop_normal_model_lanes failed' }

Log 'Starting evaluator :11436'
& (Join-Path $PSScriptRoot 'start_235b_evaluator_lane.ps1')
if ($LASTEXITCODE -ne 0) { throw 'start_235b_evaluator_lane failed' }

$modelsJson = curl.exe -s -m 30 http://127.0.0.1:11436/v1/models
if ($modelsJson -notmatch 'qwen3:235b') { throw 'qwen3:235b not on :11436' }
Log '235B lane ready'

$py = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }

foreach ($section in $Sections) {
    Log "Evaluating section $section"
    $sectionLog = Join-Path $logDir "235b_section${section}_eval.log"
    & $py (Join-Path $Root 'run_235b_eval_section.py') $section '--isolated' '--overwrite' 2>&1 | Tee-Object -FilePath $sectionLog
    if ($LASTEXITCODE -ne 0) {
        Log "Section $section failed (exit $LASTEXITCODE)"
        & (Join-Path $PSScriptRoot 'stop_235b_evaluator_lane.ps1') -ForceStopOllamaApp | Out-Null
        exit $LASTEXITCODE
    }
    Log "Section $section report saved"
}

Log 'Stopping evaluator lane'
& (Join-Path $PSScriptRoot 'stop_235b_evaluator_lane.ps1') -ForceStopOllamaApp | Out-Null
Log 'All sections complete.'
