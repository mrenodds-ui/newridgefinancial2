<#
.SYNOPSIS
  Register NewRidgeFinancial 2.0 (Start Program / port 8765) to start at every Windows sign-in.

.DESCRIPTION
  Creates a logon scheduled task (and Startup-folder shortcut) that launches the NR2
  browser server in the background. Does not open a browser window on reboot.
#>
[CmdletBinding()]
param(
    [string]$TaskName = 'New Ridge NR2 Program',
    [switch]$OpenBrowser,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$StartScript = Join-Path $PSScriptRoot 'start_nr2_browser.ps1'
$Nr2Scripts = Join-Path $Root 'NewRidgeFinancial2\scripts'
$HiddenHelper = Join-Path $Nr2Scripts 'Get-HiddenPowerShellLauncher.ps1'

function Write-Info([string]$Message) {
    if (-not $Quiet) { Write-Host $Message }
}

if (-not (Test-Path $StartScript)) {
    throw "Start script not found: $StartScript"
}
if (-not (Test-Path $HiddenHelper)) {
    throw "Hidden launcher helper not found: $HiddenHelper"
}

. $HiddenHelper

$extra = @('-NoBrowser', '-SkipValidation', '-SkipModelWarmup')
if ($OpenBrowser) {
    $extra = @('-SkipValidation', '-SkipModelWarmup')
}

$taskCommand = Get-HiddenPowerShellTaskCommand -ScriptPath $StartScript -ExtraArgs $extra

# Prefer Register-ScheduledTask for AtLogOn + battery-friendly settings.
$launcher = Get-HiddenPowerShellLauncher
$argLine = if ($launcher.Kind -eq 'pythonw') {
    "`"$($launcher.Launcher)`" `"$StartScript`" $($extra -join ' ')"
} else {
    "//B //Nologo `"$($launcher.Launcher)`" `"$StartScript`" $($extra -join ' ')"
}

try {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
} catch {}

$action = New-ScheduledTaskAction `
    -Execute $launcher.Execute `
    -Argument $argLine `
    -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description 'Starts NewRidgeFinancial 2.0 (Apex Bridge on 127.0.0.1:8765) at Windows sign-in.' | Out-Null

Write-Info "Scheduled task: $TaskName (At logon)"
Write-Info "Command: $($launcher.Execute) $argLine"

# Startup-folder shortcut as a second path (same pattern as NR2 Workstation).
$startup = [Environment]::GetFolderPath('Startup')
if ($startup) {
    $linkPath = Join-Path $startup 'NR2 Start Program.lnk'
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($linkPath)
    $shortcut.TargetPath = $launcher.Execute
    $shortcut.Arguments = $argLine
    $shortcut.WorkingDirectory = $Root
    $shortcut.WindowStyle = 7
    $shortcut.Description = 'NewRidgeFinancial 2.0 auto-start (port 8765)'
    $icon = Join-Path $Root 'NewRidgeFinancial2\site\favicon.ico'
    if (Test-Path $icon) { $shortcut.IconLocation = "$icon,0" }
    $shortcut.Save()
    Write-Info "Startup shortcut: $linkPath"
}

if (-not $Quiet) {
    Write-Info ''
    Write-Info 'NR2 Start Program will launch in the background after every reboot/sign-in.'
    Write-Info 'Open https://127.0.0.1:8765/ when you need the UI (or re-run with -OpenBrowser).'
    Write-Info "Verify:  schtasks /Query /TN `"$TaskName`" /FO LIST"
    Write-Info "Run now: schtasks /Run /TN `"$TaskName`""
    Write-Info "Remove:  Unregister-ScheduledTask -TaskName `"$TaskName`" -Confirm:`$false"
}
