<#
.SYNOPSIS
  Stop qwen3:235b and the evaluator Ollama lane on :11436.

.DESCRIPTION
  Stops the model tag, then stops only the listener bound to the evaluator port.
  Does not stop :11434 or :11435.

.PARAMETER WhatIf
  Show planned actions without stopping processes.

.PARAMETER Port
  Evaluator port (default 11436).

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop_235b_evaluator_lane.ps1
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$Help,

    [int]$Port = 11436,
    [string]$HostName = '127.0.0.1'
)

if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path -Full
    exit 0
}

$ErrorActionPreference = 'Continue'

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
    $listenerPids = @()
    $patterns = @(
        "127.0.0.1:$ListenPort\s",
        "0.0.0.0:$ListenPort\s",
        "\[::\]:$ListenPort\s"
    )
    foreach ($pattern in $patterns) {
        foreach ($line in (netstat -ano | Select-String $pattern)) {
            $listenerPid = [int](($line -split '\s+')[-1])
            if ($listenerPid -gt 0) {
                $listenerPids += $listenerPid
            }
        }
    }
    return $listenerPids | Select-Object -Unique
}

function Stop-ListenerOnPort([int]$ListenPort) {
    foreach ($listenerPid in Get-ListenerPidsOnPort -ListenPort $ListenPort) {
        if ($PSCmdlet.ShouldProcess("PID $listenerPid on :$ListenPort", 'Stop-Process')) {
            Write-Host "Stopping evaluator serve PID $listenerPid on :$ListenPort"
            Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
        }
    }
}

$evalHost = "${HostName}:$Port"
$env:OLLAMA_HOST = $evalHost

Write-Host 'Stopping qwen3:235b on evaluator lane...'
if ($PSCmdlet.ShouldProcess('qwen3:235b', 'ollama stop')) {
    ollama stop qwen3:235b 2>$null | Out-Null
}

Stop-ListenerOnPort -ListenPort $Port

if (-not $WhatIfPreference) {
    Start-Sleep -Seconds 2
}

if (Test-OllamaLane $evalHost) {
    Write-Error "Evaluator lane still responds on http://$evalHost. Press Ctrl+C in any foreground ollama serve terminal on :$Port, then re-run."
    exit 1
}

Write-Host "Evaluator lane is down (http://$evalHost)."
exit 0
