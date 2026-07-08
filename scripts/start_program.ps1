<#
.SYNOPSIS
  Start Program — launch NewRidgeFinancial 2.0 browser app (loopback HTTP + default browser).
#>
[CmdletBinding()]
param(
    [switch]$SkipModelWarmup,
    [switch]$Restart,
    [switch]$SkipValidation
)

$ErrorActionPreference = 'Stop'
$StartScript = Join-Path $PSScriptRoot 'start_nr2_browser.ps1'
if (-not (Test-Path $StartScript)) {
    throw "Browser start script not found: $StartScript"
}

$splat = @{}
if ($SkipModelWarmup) { $splat.SkipModelWarmup = $true }
if ($Restart) { $splat.Restart = $true }
if ($SkipValidation) { $splat.SkipValidation = $true }

& $StartScript @splat
