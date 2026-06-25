<#
.SYNOPSIS
  Stop qwen3:235b and the evaluator Ollama lane on :11436.

.DESCRIPTION
  Stops only the LISTENING process bound to the evaluator port (with retries for tray respawn).
  Does not call ollama stop; unloading qwen3:235b via ollama stop can hang during automation.
  Exits 0 immediately when :11436 has no listener.

.PARAMETER WhatIf
  Show planned actions without stopping processes.

.PARAMETER Port
  Evaluator port (default 11436).

.PARAMETER ForceStopOllamaApp
  Stop the Windows Ollama tray app when listeners keep respawning on the evaluator port.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop_235b_evaluator_lane.ps1
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$Help,

    [int]$Port = 11436,
    [string]$HostName = '127.0.0.1',
    [switch]$ForceStopOllamaApp
)

if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path -Full
    exit 0
}

$ErrorActionPreference = 'Continue'

function Get-ListenerPidsOnPort([int]$ListenPort) {
    $listenerPids = @()
    foreach ($line in (netstat -ano | Select-String 'LISTENING')) {
        $parts = ($line.ToString().Trim() -split '\s+')
        if ($parts.Count -lt 5) { continue }
        $localAddress = $parts[1]
        if ($localAddress -notmatch ":$ListenPort`$") { continue }
        $listenerPid = [int]$parts[-1]
        if ($listenerPid -gt 0) {
            $listenerPids += $listenerPid
        }
    }
    return $listenerPids | Select-Object -Unique
}

function Stop-ListenerOnPort([int]$ListenPort) {
    foreach ($listenerPid in Get-ListenerPidsOnPort -ListenPort $ListenPort) {
        if ($PSCmdlet.ShouldProcess("PID $listenerPid on :$ListenPort", 'taskkill /F')) {
            Write-Host "Stopping evaluator serve PID $listenerPid on :$ListenPort"
            & taskkill.exe /F /PID $listenerPid 2>$null | Out-Null
        }
    }
}

function Test-PortListening([int]$ListenPort) {
    return (Get-ListenerPidsOnPort -ListenPort $ListenPort).Count -gt 0
}

$evalHost = "${HostName}:$Port"
$env:OLLAMA_HOST = $evalHost

if (-not (Test-PortListening -ListenPort $Port)) {
    Write-Host "Evaluator lane already down (http://$evalHost)."
    exit 0
}

Write-Host "Stopping evaluator lane on http://$evalHost..."
if ($ForceStopOllamaApp) {
    $tray = Get-Process -Name 'ollama app' -ErrorAction SilentlyContinue
    if ($tray -and $PSCmdlet.ShouldProcess('ollama app tray', 'Stop-Process')) {
        Write-Host 'ForceStopOllamaApp: stopping Ollama tray app before evaluator teardown.'
        $tray | Stop-Process -Force -ErrorAction SilentlyContinue
        if (-not $WhatIfPreference) { Start-Sleep -Seconds 1 }
    }
}
for ($pass = 1; $pass -le 3; $pass++) {
    Stop-ListenerOnPort -ListenPort $Port
    if (-not (Test-PortListening -ListenPort $Port)) {
        break
    }
    if ($pass -lt 3 -and -not $WhatIfPreference) {
        Write-Host "Evaluator port still has listeners; retrying stop ($pass/3)..."
        Start-Sleep -Seconds 2
    }
}

if (-not $WhatIfPreference) {
    Start-Sleep -Seconds 2
}

if (Test-PortListening -ListenPort $Port) {
    if ($ForceStopOllamaApp) {
        $tray = Get-Process -Name 'ollama app' -ErrorAction SilentlyContinue
        if ($tray -and $PSCmdlet.ShouldProcess('ollama app tray', 'Stop-Process')) {
            Write-Host 'ForceStopOllamaApp: stopping Ollama tray app (optional, may affect other Ollama use).'
            $tray | Stop-Process -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
            Stop-ListenerOnPort -ListenPort $Port
        }
    }
}

if (Test-PortListening -ListenPort $Port) {
    Write-Error "Evaluator port :$Port still has listeners. Press Ctrl+C in any foreground ollama serve terminal on :$Port, then re-run."
    exit 1
}

Write-Host "Evaluator lane is down (http://$evalHost)."
exit 0
