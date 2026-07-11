[CmdletBinding()]
param(
    [string]$TaskName = "New Ridge HAL Full Practice Pull",
    [string]$RunTime = "06:00",
    [switch]$VerifyHal
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$nr2Root = Split-Path -Parent $scriptRoot
$pullScript = Join-Path $scriptRoot "Pull-HAL-Full-Practice-Sources.ps1"
. (Join-Path $nr2Root "scripts\Get-HiddenPowerShellLauncher.ps1")

if (-not (Test-Path $pullScript)) {
    throw "Pull script not found: $pullScript"
}

$extra = @()
if ($VerifyHal) { $extra += "-VerifyHal" }
$taskCommand = Get-HiddenPowerShellTaskCommand -ScriptPath $pullScript -ExtraArgs $extra

schtasks.exe /Create /TN $TaskName /SC DAILY /ST $RunTime /TR $taskCommand /F
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create or update scheduled task '$TaskName'."
}

Write-Host "Scheduled task '$TaskName' registered (hidden). Runs daily at $RunTime."
Write-Host "Command: $taskCommand"
Write-Host "To run now: schtasks /Run /TN `"$TaskName`""
Write-Host "To verify: schtasks /Query /TN `"$TaskName`" /FO LIST"
