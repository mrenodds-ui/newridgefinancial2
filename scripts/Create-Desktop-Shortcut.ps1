<#
.SYNOPSIS
  Create (or refresh) Desktop shortcuts that launch NewRidgeFinancial 2.0.

.DESCRIPTION
  Delegates to Refresh-NR2-DesktopShortcut.ps1 so local Desktop and OneDrive Desktop stay in sync.
#>
[CmdletBinding()]
param(
    [string]$Name = 'New Ridge Financial'
)

$ErrorActionPreference = 'Stop'
$Refresh = Join-Path $PSScriptRoot 'Refresh-NR2-DesktopShortcut.ps1'
if (-not (Test-Path $Refresh)) { throw "Refresh script not found: $Refresh" }
& $Refresh -Name $Name
