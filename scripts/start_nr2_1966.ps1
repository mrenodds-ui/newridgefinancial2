<#
.SYNOPSIS
  Deprecated alias — use scripts/start_nr2_desktop.ps1 (port 8765, not 1966).
#>
[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$Restart,
    [switch]$SkipModelWarmup,
    [switch]$SkipValidation
)

Write-Host 'Note: start_nr2_1966.ps1 is deprecated. Using start_nr2_desktop.ps1 on port 8765.' -ForegroundColor Yellow
$StartScript = Join-Path $PSScriptRoot 'start_nr2_desktop.ps1'
& $StartScript @PSBoundParameters
