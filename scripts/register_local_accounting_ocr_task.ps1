[CmdletBinding()]
param(
    [string]$TaskName = 'New Ridge Local Accounting OCR',
    [string]$InboxPath = '',
    [string]$ArchivePath = '',
    [string]$DbPath = '',
    [int]$RepeatMinutes = 30
)

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$runnerScript = Join-Path $scriptRoot 'process_financial_document_inbox.ps1'

if (-not $InboxPath) {
    $InboxPath = Join-Path $scriptRoot '..\app_data\nr2\document_inbox'
}
if (-not $ArchivePath) {
    $ArchivePath = Join-Path $scriptRoot '..\app_data\nr2\document_inbox\processed'
}

New-Item -ItemType Directory -Force -Path $InboxPath | Out-Null
New-Item -ItemType Directory -Force -Path $ArchivePath | Out-Null

$defaultInboxPath = Join-Path $scriptRoot '..\app_data\nr2\document_inbox'
$defaultArchivePath = Join-Path $scriptRoot '..\app_data\nr2\document_inbox\processed'

$taskCommand = "powershell.exe -ExecutionPolicy Bypass -File `"$runnerScript`""
$taskCommand = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runnerScript`""
if ($InboxPath -and ((Resolve-Path $InboxPath).Path -ne (Resolve-Path $defaultInboxPath).Path)) {
    $taskCommand += " -InboxPath `"$InboxPath`""
}
if ($ArchivePath -and ((Resolve-Path $ArchivePath).Path -ne (Resolve-Path $defaultArchivePath).Path)) {
    $taskCommand += " -ArchivePath `"$ArchivePath`""
}
if ($DbPath) {
    $taskCommand += " -DbPath `"$DbPath`""
}

schtasks.exe /Create /TN $TaskName /SC MINUTE /MO $RepeatMinutes /TR $taskCommand /F | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create or update scheduled task '$TaskName'."
}

Write-Host "Scheduled task '$TaskName' created or updated."
Write-Host "Command: $taskCommand"