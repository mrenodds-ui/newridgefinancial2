<#
.SYNOPSIS
  Run Gemma 2 HAL programming error review (9B or 27B).

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_gemma2_hal_program_eval.ps1 -Size 9b
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_gemma2_hal_program_eval.ps1 -Both
#>
[CmdletBinding()]
param(
    [ValidateSet('9b', '27b')]
    [string]$Size = '9b',
    [switch]$Both,
    [string]$OllamaUrl = 'http://127.0.0.1:11434',
    [switch]$RebuildContext,
    [switch]$SkipPull,
    [switch]$UnloadDailyLanes,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

function Invoke-Gemma2HalEval {
    param(
        [Parameter(Mandatory = $true)][string]$EvalSize,
        [switch]$SkipContextBuild,
        [switch]$SkipModelPull
    )

    $profilesPath = Join-Path $Root 'evals\local_model_profiles.json'
    $profiles = Get-Content $profilesPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($EvalSize -eq '27b') {
        $alias = 'gemma2_hal_27b'
    } else {
        $alias = 'gemma2_hal_9b'
    }
    $profile = $profiles.profiles.$alias
    if (-not $profile) {
        throw "Profile not found: $alias"
    }

    Write-Host "=== Gemma 2 HAL review - $EvalSize ($($profile.model)) ===" -ForegroundColor Cyan

    if (-not $SkipModelPull -and -not $SkipPull -and $profile.ollama_pull) {
        Write-Host "Ensuring model: $($profile.ollama_pull)" -ForegroundColor DarkGray
        $pullSteps = [regex]::Split($profile.ollama_pull, '\s&&\s')
        foreach ($step in $pullSteps) {
            if (-not $step.Trim()) { continue }
            Invoke-Expression $step.Trim()
            if ($LASTEXITCODE -ne 0) {
                throw "ollama_pull step failed for ${alias}: $step"
            }
        }
    }

    if (-not $SkipContextBuild) {
        & (Join-Path $PSScriptRoot 'build_gemma2_hal_program_context.ps1')
    }

    $py = Join-Path $Root '.venv\Scripts\python.exe'
    if (-not (Test-Path $py)) {
        $py = 'python'
    }

    $env:GEMMA2_HAL_SIZE = $EvalSize
    $env:GEMMA2_HAL_OLLAMA_URL = $OllamaUrl

    $argsList = @(
        (Join-Path $Root 'run_gemma2_hal_program_eval.py'),
        '--size', $EvalSize,
        '--base-url', $OllamaUrl
    )
    if ($RebuildContext -and -not $SkipContextBuild) {
        $argsList += '--rebuild-context'
    }
    if ($DryRun) {
        $argsList += '--dry-run'
    }

    & $py @argsList
    if ($LASTEXITCODE -ne 0) {
        throw "Gemma 2 $EvalSize eval failed (exit $LASTEXITCODE)"
    }
}

if ($Both) {
    Write-Host 'Running 9B + 27B HAL programming reviews (sequential on one Ollama lane)' -ForegroundColor Cyan
    $UnloadDailyLanes = $true
}

if ($UnloadDailyLanes -or $Both -or $Size -eq '27b') {
    Write-Host 'Stopping daily GPU lanes for 27B headroom...' -ForegroundColor Yellow
    $stopScript = Join-Path $PSScriptRoot 'stop_normal_model_lanes.ps1'
    if (Test-Path $stopScript) {
        powershell -NoProfile -ExecutionPolicy Bypass -File $stopScript -ForceStopOllamaApp 2>$null | Out-Null
        Start-Sleep -Seconds 2
    } else {
        Get-Process ollama -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
}

if ($Both) {
    Invoke-Gemma2HalEval -EvalSize '9b'
    if ($SkipPull) {
        Invoke-Gemma2HalEval -EvalSize '27b' -SkipContextBuild -SkipModelPull
    } else {
        Invoke-Gemma2HalEval -EvalSize '27b' -SkipContextBuild
    }
    Write-Host 'Both reports ready: gemma2_hal_program_9b_report.md, gemma2_hal_program_27b_report.md' -ForegroundColor Green
    exit 0
}

Invoke-Gemma2HalEval -EvalSize $Size
exit 0
