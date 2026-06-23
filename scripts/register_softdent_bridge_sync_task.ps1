[CmdletBinding()]
param(
    [string]$TaskName = 'New Ridge SoftDent Bridge Sync',
    [int]$RepeatMinutes = 15
)

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$syncScript = Join-Path $scriptRoot 'scheduled_softdent_bridge_sync.ps1'

if (-not (Test-Path $syncScript)) {
    throw "Sync script not found at $syncScript"
}

$taskCommand = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$syncScript`""

schtasks.exe /Create /TN $TaskName /SC MINUTE /MO $RepeatMinutes /TR $taskCommand /F
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create or update scheduled task '$TaskName'."
}

Write-Host "Scheduled task '$TaskName' registered. Runs every $RepeatMinutes minute(s)."
Write-Host "Command: $taskCommand"
Write-Host "To verify: schtasks /Query /TN `"$TaskName`" /FO LIST"
Write-Host "To run now: schtasks /Run /TN `"$TaskName`""
