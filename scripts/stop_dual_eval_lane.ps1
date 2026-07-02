<#
.SYNOPSIS
  Stop dual-model eval Ollama lane (default :11438).
#>
[CmdletBinding()]
param(
    [switch]$Help,
    [int]$Port = 11438,
    [switch]$ForceStopOllamaApp
)

if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path -Full
    exit 0
}

$ErrorActionPreference = 'Stop'
$stopScript = Join-Path $PSScriptRoot 'stop_235b_evaluator_lane.ps1'
if ($ForceStopOllamaApp) {
    & $stopScript -Port $Port -ForceStopOllamaApp
} else {
    & $stopScript -Port $Port
}
exit $LASTEXITCODE
