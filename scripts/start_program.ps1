<#
.SYNOPSIS
  Start Program — launch NewRidgeFinancial 2.0 desktop app (pywebview, no browser).
#>
[CmdletBinding()]
param(
    [switch]$SkipModelWarmup,
    [switch]$Restart,
    [switch]$SkipValidation
)

$ErrorActionPreference = 'Stop'
$StartScript = Join-Path $PSScriptRoot 'start_nr2_desktop.ps1'
if (-not (Test-Path $StartScript)) {
    throw "Desktop start script not found: $StartScript"
}

$argsList = @()
if ($SkipModelWarmup) { $argsList += '-SkipModelWarmup' }
if ($Restart) { $argsList += '-Restart' }
if ($SkipValidation) { $argsList += '-SkipValidation' }

& $StartScript @argsList
