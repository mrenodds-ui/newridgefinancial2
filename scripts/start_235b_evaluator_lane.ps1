<#
.SYNOPSIS
  Start the isolated 235B evaluator Ollama lane on :11436.

.DESCRIPTION
  Requires :11434 and :11435 to be down. By default starts ollama serve in the
  background and logs to .local_logs/. For manual control, use -ForegroundInstructions
  to print the foreground command instead of starting a process.

.PARAMETER Port
  Evaluator port (default 11436).

.PARAMETER HostName
  Bind host (default 127.0.0.1).

.PARAMETER ForegroundInstructions
  Print foreground ollama serve steps; do not start a background process.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_235b_evaluator_lane.ps1
#>
[CmdletBinding()]
param(
    [switch]$Help,

    [int]$Port = 11436,
    [string]$HostName = '127.0.0.1',
    [switch]$ForegroundInstructions
)

if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path -Full
    exit 0
}

$ErrorActionPreference = 'Stop'

function Test-OllamaLane([string]$HostPort) {
    try {
        Invoke-WebRequest -Uri "http://$HostPort/v1/models" -TimeoutSec 5 -UseBasicParsing | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Get-ListenerPidsOnPort([int]$ListenPort) {
    $pids = @()
    $patterns = @(
        "127.0.0.1:$ListenPort\s",
        "0.0.0.0:$ListenPort\s",
        "\[::\]:$ListenPort\s"
    )
    foreach ($pattern in $patterns) {
        foreach ($line in (netstat -ano | Select-String $pattern)) {
            $pid = [int](($line -split '\s+')[-1])
            if ($pid -gt 0) {
                $pids += $pid
            }
        }
    }
    return $pids | Select-Object -Unique
}

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw 'ollama is required but was not found on PATH.'
}

$lane11434 = Test-OllamaLane '127.0.0.1:11434'
$lane11435 = Test-OllamaLane '127.0.0.1:11435'
if ($lane11434 -or $lane11435) {
    throw 'Normal lanes must be stopped before starting the 235B evaluator. Run scripts/stop_normal_model_lanes.ps1 first.'
}

$evalHost = "${HostName}:$Port"
if (Test-OllamaLane $evalHost) {
    Write-Host "Evaluator lane already up at http://$evalHost"
    exit 0
}

$occupied = Get-ListenerPidsOnPort -ListenPort $Port
if ($occupied.Count -gt 0) {
    throw "Port :$Port is in use (PID $($occupied -join ', ')) but /v1/models is not healthy. Free the port before starting the evaluator."
}

if ($ForegroundInstructions) {
    Write-Host @"
Foreground evaluator lane (recommended for long runs):
  1. Open a dedicated PowerShell terminal.
  2. `$env:OLLAMA_HOST = '$evalHost'
  3. ollama serve
  Keep that terminal open until the section completes.
"@
    exit 0
}

$env:OLLAMA_HOST = $evalHost
$repoRoot = Join-Path $PSScriptRoot '..'
$logDir = Join-Path $repoRoot '.local_logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "ollama_evaluator_${Port}.log"

Write-Host "Starting Ollama evaluator serve on http://$evalHost (log: $logFile)"
Write-Host 'Note: ollama serve is a long-running process. This script starts it in the background for automation.'
Write-Host 'For interactive use, re-run with -ForegroundInstructions and start serve in a dedicated terminal.'

$proc = Start-Process -FilePath 'ollama' -ArgumentList 'serve' -PassThru -WindowStyle Hidden -RedirectStandardOutput $logFile -RedirectStandardError $logFile
Start-Sleep -Seconds 3

if (-not (Test-OllamaLane $evalHost)) {
    throw "Evaluator lane failed to start on http://$evalHost. Check $logFile"
}

Write-Host "Evaluator lane is up (pid $($proc.Id))."
exit 0
