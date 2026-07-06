[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('1', '2', '3', '4', '5', '1a', '1b', '1c', '2a', '2b', '2c', '1a1', '1a2', '1b1', '1b2', '1c1', '1c2', '2a1', '2a2', '2b1', '2b2', '2c1', '2c2')]
    [string]$Section,

    [switch]$OverwriteReport,
    [switch]$ForceStopOllamaApp
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $repoRoot

function Get-ListenerPidsOnPort([int]$Port) {
    $listenerPids = @()
    foreach ($line in (netstat -ano | Select-String 'LISTENING')) {
        $parts = ($line.ToString().Trim() -split '\s+')
        if ($parts.Count -lt 5) {
            continue
        }

        $localAddress = $parts[1]
        if ($localAddress -notmatch ":$Port`$") {
            continue
        }

        $listenerPid = [int]$parts[-1]
        if ($listenerPid -gt 0) {
            $listenerPids += $listenerPid
        }
    }

    return $listenerPids | Select-Object -Unique
}

function Stop-PortListeners([int[]]$Ports) {
    foreach ($port in $Ports) {
        foreach ($pid in Get-ListenerPidsOnPort -Port $port) {
            Write-Host "Stopping PID $pid listening on :$port"
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
}

$logDir = Join-Path $repoRoot '.local_logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$preflightLog = Join-Path $logDir "235b_preflight_${Section}.log"
$sectionLog = Join-Path $logDir "235b_section_${Section}.log"

if (Test-Path $preflightLog) {
    Remove-Item $preflightLog -Force
}

if (Test-Path $sectionLog) {
    Remove-Item $sectionLog -Force
}

& (Join-Path $PSScriptRoot 'stop_235b_evaluator_lane.ps1') -ForceStopOllamaApp:$ForceStopOllamaApp *> $preflightLog
Write-Host 'Stopping normal lanes directly on :11434 and :11435' *>> $preflightLog
if ($ForceStopOllamaApp) {
    $tray = Get-Process -Name 'ollama app' -ErrorAction SilentlyContinue
    if ($tray) {
        Write-Host 'Stopping Ollama tray app' *>> $preflightLog
        $tray | Stop-Process -Force -ErrorAction SilentlyContinue
    }
}

Stop-PortListeners -Ports @(11434, 11435) *>> $preflightLog

& (Join-Path $PSScriptRoot 'start_235b_evaluator_lane.ps1') *>> $preflightLog
if ($LASTEXITCODE -ne 0) {
    Add-Content $preflightLog "START_EXIT=$LASTEXITCODE"
    exit $LASTEXITCODE
}

$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    $python = 'python'
}

$args = @(
    Join-Path $repoRoot 'run_235b_eval_section.py'
    $Section
    '--isolated'
)

if ($OverwriteReport) {
    $args += '--overwrite'
}

& $python @args *> $sectionLog
$pythonExit = $LASTEXITCODE
Add-Content $sectionLog "PY_EXIT=$pythonExit"
exit $pythonExit