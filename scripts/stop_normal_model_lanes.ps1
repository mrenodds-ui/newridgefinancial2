<#
.SYNOPSIS
  Stop normal 24B (:11434) and 30B (:11435) Ollama lanes before a 235B evaluation.

.DESCRIPTION
  Stops model tags on each port, then stops listeners bound to :11434 and :11435.
  Verifies both lanes are down before exiting 0.

  Optional -ForceStopOllamaApp stops the Windows Ollama tray app when it keeps
  respawning :11434. This is off by default because it affects unrelated Ollama use.

.PARAMETER WhatIf
  Show planned actions without stopping processes or models.

.PARAMETER ForceStopOllamaApp
  Stop "ollama app" (tray) after model stops. Use only when :11434 respawns.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop_normal_model_lanes.ps1
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$Help,

    [switch]$ForceStopOllamaApp
)

if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path -Full
    exit 0
}

$ErrorActionPreference = 'Continue'

function Test-OllamaLane([string]$HostPort) {
    try {
        $resp = Invoke-WebRequest -Uri "http://$HostPort/v1/models" -TimeoutSec 5 -UseBasicParsing
        return @{ Up = $true; Status = $resp.StatusCode }
    }
    catch {
        return @{ Up = $false; Error = $_.Exception.Message }
    }
}

function Get-ListenerPidsOnPort([int]$Port) {
    $listenerPids = @()
    $patterns = @(
        "127.0.0.1:$Port\s",
        "0.0.0.0:$Port\s",
        "\[::\]:$Port\s"
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

function Stop-ListenerOnPort([int]$Port) {
    foreach ($listenerPid in Get-ListenerPidsOnPort -Port $Port) {
        if ($PSCmdlet.ShouldProcess("PID $listenerPid on :$Port", 'Stop-Process')) {
            Write-Host "Stopping PID $listenerPid listening on :$Port"
            Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host 'Stopping normal model lanes (24B :11434, 30B :11435)...'

if ($PSCmdlet.ShouldProcess('mistral-small3.1:24b on :11434', 'ollama stop')) {
    $env:OLLAMA_HOST = '127.0.0.1:11434'
    ollama stop mistral-small3.1:24b 2>$null | Out-Null
}

if ($PSCmdlet.ShouldProcess('qwen3:30b on :11435', 'ollama stop')) {
    $env:OLLAMA_HOST = '127.0.0.1:11435'
    ollama stop qwen3:30b 2>$null | Out-Null
}

Stop-ListenerOnPort -Port 11434
Stop-ListenerOnPort -Port 11435

if ($ForceStopOllamaApp) {
    $tray = Get-Process -Name 'ollama app' -ErrorAction SilentlyContinue
    if ($tray -and $PSCmdlet.ShouldProcess('ollama app tray', 'Stop-Process')) {
        Write-Host 'ForceStopOllamaApp: stopping Ollama tray app (optional, may affect other Ollama use).'
        $tray | Stop-Process -Force -ErrorAction SilentlyContinue
    }
}

if (-not $WhatIfPreference) {
    Start-Sleep -Seconds 2
}

$lane11434 = Test-OllamaLane '127.0.0.1:11434'
$lane11435 = Test-OllamaLane '127.0.0.1:11435'

if ($lane11434.Up -or $lane11435.Up) {
    Write-Error @(
        'Normal lanes still respond on :11434 or :11435.',
        'Stop foreground scripts/run_frontend_model.ps1 and scripts/run_backend_model.ps1 (Ctrl+C),',
        'or re-run with -ForceStopOllamaApp if the tray app keeps respawning :11434.'
    ) -join ' '
    exit 1
}

Write-Host 'Normal lanes are down.'
exit 0
