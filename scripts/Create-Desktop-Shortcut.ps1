<#
.SYNOPSIS
  Create (or refresh) a Desktop shortcut that launches NewRidgeFinancial 2.0.

.DESCRIPTION
  Places "New Ridge Financial.lnk" on the current user's Desktop, pointing at
  StartNewRidgeFinancial2.bat with the branded NR2 icon. Safe to re-run.
#>
[CmdletBinding()]
param(
    [string]$Name = 'New Ridge Financial'
)

$ErrorActionPreference = 'Stop'

$Root      = Split-Path $PSScriptRoot -Parent
$Target    = Join-Path $Root 'StartNewRidgeFinancial2.bat'
$Icon      = Join-Path $Root 'assets\nr2-icon.ico'

if (-not (Test-Path $Target)) { throw "Start script not found: $Target" }

$desktop  = [Environment]::GetFolderPath('Desktop')
$linkPath = Join-Path $desktop ("{0}.lnk" -f $Name)

$shell    = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($linkPath)
$shortcut.TargetPath       = $Target
$shortcut.WorkingDirectory = $Root
if (Test-Path $Icon) { $shortcut.IconLocation = "$Icon,0" }
$shortcut.Description       = 'Launch NewRidgeFinancial 2.0 desktop app'
$shortcut.WindowStyle       = 7   # launcher console starts minimized
$shortcut.Save()

Write-Host "Desktop shortcut created: $linkPath" -ForegroundColor Green
