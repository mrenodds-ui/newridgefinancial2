[CmdletBinding()]
param(
    [string]$TaskName = "New Ridge HAL Full Practice Pull",
    [string]$RunTime = "06:00",
    [switch]$VerifyHal
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pullScript = Join-Path $scriptRoot "Pull-HAL-Full-Practice-Sources.ps1"

if (-not (Test-Path $pullScript)) {
    throw "Pull script not found: $pullScript"
}

$verifyFlag = if ($VerifyHal) { " -VerifyHal" } else { "" }
$taskCommand = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$pullScript`"$verifyFlag"

schtasks.exe /Create /TN $TaskName /SC DAILY /ST $RunTime /TR $taskCommand /F
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create or update scheduled task '$TaskName'."
}

Write-Host "Scheduled task '$TaskName' registered. Runs daily at $RunTime."
Write-Host "Command: $taskCommand"
Write-Host "To run now: schtasks /Run /TN `"$TaskName`""
Write-Host "To verify: schtasks /Query /TN `"$TaskName`" /FO LIST"
