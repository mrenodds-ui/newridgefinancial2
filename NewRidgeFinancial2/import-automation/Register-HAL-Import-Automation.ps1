[CmdletBinding()]
param(
    [string]$TaskName = "New Ridge HAL Import Sync",
    [int]$RepeatMinutes = 5,
    [string]$SoftDentSource = $env:NR2_SOFTDENT_EXPORT_SOURCE,
    [string]$QuickBooksSource = $env:NR2_QUICKBOOKS_EXPORT_SOURCE
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$syncScript = Join-Path $scriptRoot "Sync-HAL-Imports.ps1"

if (-not (Test-Path $syncScript)) {
    throw "Sync script not found: $syncScript"
}

$arguments = @(
    "-NoProfile",
    "-WindowStyle Hidden",
    "-ExecutionPolicy Bypass",
    "-File `"$syncScript`""
)

if (-not [string]::IsNullOrWhiteSpace($SoftDentSource)) {
    $arguments += "-SoftDentSource `"$SoftDentSource`""
}

if (-not [string]::IsNullOrWhiteSpace($QuickBooksSource)) {
    $arguments += "-QuickBooksSource `"$QuickBooksSource`""
}

$taskCommand = "powershell.exe " + ($arguments -join " ")

schtasks.exe /Create /TN $TaskName /SC MINUTE /MO $RepeatMinutes /TR $taskCommand /F
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create or update scheduled task '$TaskName'."
}

Write-Host "Scheduled task '$TaskName' registered. Runs every $RepeatMinutes minute(s)."
Write-Host "Command: $taskCommand"
Write-Host "To run now: schtasks /Run /TN `"$TaskName`""
Write-Host "To verify: schtasks /Query /TN `"$TaskName`" /FO LIST"
