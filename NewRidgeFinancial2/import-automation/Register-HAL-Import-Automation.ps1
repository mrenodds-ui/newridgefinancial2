[CmdletBinding()]
param(
    [string]$TaskName = "New Ridge HAL Import Sync",
    [int]$RepeatMinutes = 5,
    [string]$SoftDentSource = $env:NR2_SOFTDENT_EXPORT_SOURCE,
    [string]$QuickBooksSource = $env:NR2_QUICKBOOKS_EXPORT_SOURCE
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$nr2Root = Split-Path -Parent $scriptRoot
$syncScript = Join-Path $scriptRoot "Sync-HAL-Imports.ps1"
. (Join-Path $nr2Root "scripts\Get-HiddenPowerShellLauncher.ps1")

if (-not (Test-Path $syncScript)) {
    throw "Sync script not found: $syncScript"
}

$psArgs = @()
if (-not [string]::IsNullOrWhiteSpace($SoftDentSource)) {
    $psArgs += "-SoftDentSource `"$SoftDentSource`""
}
if (-not [string]::IsNullOrWhiteSpace($QuickBooksSource)) {
    $psArgs += "-QuickBooksSource `"$QuickBooksSource`""
}

$taskCommand = Get-HiddenPowerShellTaskCommand -ScriptPath $syncScript -ExtraArgs $psArgs

schtasks.exe /Create /TN $TaskName /SC MINUTE /MO $RepeatMinutes /TR $taskCommand /F
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create or update scheduled task '$TaskName'."
}

Write-Host "Scheduled task '$TaskName' registered (hidden). Runs every $RepeatMinutes minute(s)."
Write-Host "Command: $taskCommand"
Write-Host "To run now: schtasks /Run /TN `"$TaskName`""
Write-Host "To verify: schtasks /Query /TN `"$TaskName`" /FO LIST"
