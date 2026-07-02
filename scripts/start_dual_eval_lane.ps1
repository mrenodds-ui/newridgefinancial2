<#
.SYNOPSIS
  Start isolated dual-model eval Ollama lane (default :11438).
#>
[CmdletBinding()]
param(
    [switch]$Help,
    [int]$Port = 11438,
    [string]$HostName = '127.0.0.1'
)

if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path -Full
    exit 0
}

$ErrorActionPreference = 'Stop'
$startScript = Join-Path $PSScriptRoot 'start_235b_evaluator_lane.ps1'
& $startScript -Port $Port -HostName $HostName
exit $LASTEXITCODE
