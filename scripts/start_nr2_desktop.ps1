<#
.SYNOPSIS
  Legacy entry — forwards to the NR2 browser program launcher.
#>
[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$Restart,
    [switch]$SkipModelWarmup,
    [switch]$SkipValidation
)

$ErrorActionPreference = 'Stop'
$BrowserScript = Join-Path $PSScriptRoot 'start_nr2_browser.ps1'
if (-not (Test-Path $BrowserScript)) {
    throw "Browser start script not found: $BrowserScript"
}

$argsList = @()
if ($NoBrowser) { $argsList += '-NoBrowser' }
if ($Restart) { $argsList += '-Restart' }
if ($SkipModelWarmup) { $argsList += '-SkipModelWarmup' }
if ($SkipValidation) { $argsList += '-SkipValidation' }

& $BrowserScript @argsList
