<#
.SYNOPSIS
  Register NR2 Office Workstation to start silently at Windows sign-in.
#>
[CmdletBinding()]
param(
    [string]$PkgRoot,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'
if (-not $PkgRoot) {
    $PkgRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
}

$HiddenVbs = Join-Path $PkgRoot 'Start-NR2-Workstation-Hidden.vbs'
$HiddenBat = Join-Path $PkgRoot 'Start-NR2-Workstation-Hidden.bat'
$Icon = Join-Path $PkgRoot 'assets\nr2-icon.ico'
$TaskName = 'NR2 Workstation'

function Write-Info($msg) { if (-not $Quiet) { Write-Host $msg } }

function New-StartupShortcut {
    param(
        [string]$LinkPath,
        [string]$Target,
        [string]$Description
    )
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($LinkPath)
    $shortcut.TargetPath = $Target
    $shortcut.WorkingDirectory = $PkgRoot
    if (Test-Path $Icon) { $shortcut.IconLocation = "$Icon,0" }
    $shortcut.Description = $Description
    $shortcut.WindowStyle = 7
    $shortcut.Save()
}

if (-not (Test-Path $HiddenVbs)) {
    throw "Missing launcher: $HiddenVbs"
}

$startup = [Environment]::GetFolderPath('Startup')
if ($startup) {
    $link = Join-Path $startup 'NR2 Workstation.lnk'
    New-StartupShortcut -LinkPath $link -Target $HiddenVbs -Description 'NR2 Office Workstation auto-start'
    Write-Info "Startup shortcut: $link"
}

$wscript = (Get-Command wscript.exe -ErrorAction SilentlyContinue).Source
if (-not $wscript) { $wscript = "$env:SystemRoot\System32\wscript.exe" }

try {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }
} catch {}

$action = New-ScheduledTaskAction -Execute $wscript -Argument "`"$HiddenVbs`"" -WorkingDirectory $PkgRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 3) `
    -MultipleInstances IgnoreNew
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description 'NR2 Office Workstation — background popups and HAL at sign-in' | Out-Null
Write-Info "Scheduled task: $TaskName (At logon)"

if (-not $Quiet) {
    Write-Info ''
    Write-Info 'NR2 Workstation will start in the background at sign-in (popups + Ask HAL).'
    Write-Info 'Double-click the desktop icon to open the messenger window.'
}
