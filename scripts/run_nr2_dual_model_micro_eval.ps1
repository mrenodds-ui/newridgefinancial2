<#
.SYNOPSIS
  Run NR2 micro sections with 120B draft + 70B (llama3.3) review on :11438.
#>
[CmdletBinding()]
param(
    [ValidateSet('1a', '1b', '1c', '2a', '2b', '2c', '1a1', '1a2', '1b1', '1b2', '1c1', '1c2', '2a1', '2a2', '2b1', '2b2', '2c1', '2c2')]
    [string[]]$Sections = @('1a1', '1a2', '1b1', '1b2', '1c1', '1c2', '2a1', '2a2', '2b1', '2b2', '2c1', '2c2')
)

$ErrorActionPreference = 'Continue'
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
$logDir = Join-Path $Root '.local_logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$batchLog = Join-Path $logDir 'dual_model_micro_eval.log'

function Log([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -Path $batchLog -Value $line
    Write-Host $line
}

Log "Dual-model eval sections: $($Sections -join ', ')"
Log "Primary: gpt-oss:120b  Review: llama3.3:latest (70B class)"

& (Join-Path $PSScriptRoot 'build_235b_nr2_focus.ps1') | Out-Null

Log 'Stopping daily HAL lanes and tray Ollama'
Stop-Process -Name 'ollama app' -Force -ErrorAction SilentlyContinue
Get-Process ollama -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
& (Join-Path $PSScriptRoot 'stop_normal_model_lanes.ps1') -ForceStopOllamaApp | Out-Null

Log 'Starting eval lane :11438'
& (Join-Path $PSScriptRoot 'start_dual_eval_lane.ps1')
if ($LASTEXITCODE -ne 0) { throw 'start_dual_eval_lane failed' }

$modelsJson = curl.exe -s -m 30 http://127.0.0.1:11438/v1/models
if ($modelsJson -notmatch 'gpt-oss:120b') { throw 'gpt-oss:120b not on :11438' }
if ($modelsJson -notmatch 'llama3.3') { throw 'llama3.3 not on :11438' }
Log 'Eval lane ready on :11438'

$env:NR2_EVAL_OLLAMA_HOST = '127.0.0.1:11438'
$env:NR2_EVAL_PRIMARY_MODEL = 'gpt-oss:120b'
$env:NR2_EVAL_SECONDARY_MODEL = 'llama3.3:latest'
$py = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }

function Stop-NormalLanesForEval {
    Stop-Process -Name 'ollama app' -Force -ErrorAction SilentlyContinue
    $stopScript = Join-Path $PSScriptRoot 'stop_normal_model_lanes.ps1'
    # Run in a child shell so stop script exit codes do not kill the batch.
    powershell -NoProfile -ExecutionPolicy Bypass -File $stopScript -ForceStopOllamaApp 2>$null | Out-Null
}

foreach ($section in $Sections) {
    Log "=== Section $section (120B then 70B) ==="
    Stop-NormalLanesForEval
    $sectionLog = Join-Path $logDir "nr2_dual_slice_${section}.log"
    if (Test-Path $sectionLog) { Remove-Item -LiteralPath $sectionLog -Force }
    & $py (Join-Path $Root 'run_dual_model_eval_section.py') $section '--isolated' '--overwrite' 2>&1 | ForEach-Object {
        Add-Content -LiteralPath $sectionLog -Value $_ -Encoding utf8
        Write-Output $_
    }
    if ($LASTEXITCODE -ne 0) {
        Log "Section $section failed (exit $LASTEXITCODE)"
        & (Join-Path $PSScriptRoot 'stop_dual_eval_lane.ps1') -ForceStopOllamaApp | Out-Null
        exit $LASTEXITCODE
    }
    Log "Section $section report saved"
}

Log 'Stopping eval lane'
& (Join-Path $PSScriptRoot 'stop_dual_eval_lane.ps1') -ForceStopOllamaApp | Out-Null
Log 'Dual-model batch complete.'
