# Install HAL nightly Trellis dental eligibility verify - Mon-Thu 10:00 PM interactive.
# Playwright needs a logged-on desktop (same pattern as SoftDent 5pm GUI pull).
$ErrorActionPreference = 'Stop'

$RepoRoot = if ($env:NEWRIDGE_FINANCIAL_REPO) {
    $env:NEWRIDGE_FINANCIAL_REPO
} else {
    'C:\Users\mreno\newridgefamilyfinancial'
}
$TaskName = 'NR2 Trellis Nightly Insurance Verify 10PM Mon-Thu'
$Py = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$Script = Join-Path $RepoRoot 'scripts\run_trellis_nightly_verify.py'
$CurrentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if (!(Test-Path -LiteralPath $Py)) {
    throw "Missing venv python: $Py"
}
if (!(Test-Path -LiteralPath $Script)) {
    throw "Missing script: $Script"
}
$EnvLocal = Join-Path $RepoRoot '.env.vyne.local'
if (!(Test-Path -LiteralPath $EnvLocal)) {
    Write-Warning "Missing .env.vyne.local - create VYNE_AUTOMATION_USERNAME / PASSWORD (Wichita) before first run."
}

$action = New-ScheduledTaskAction `
    -Execute $Py `
    -Argument "`"$Script`" --force --verify" `
    -WorkingDirectory $RepoRoot

# Mon-Thu 10:00 PM
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday -At '10:00PM'

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -WakeToRun `
    -RestartCount 1 `
    -RestartInterval (New-TimeSpan -Minutes 15) `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3)

$principal = New-ScheduledTaskPrincipal -UserId $CurrentUser -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null

Write-Host "Installed '$TaskName' (Interactive / Mon-Thu 10:00 PM) for $CurrentUser."
Write-Host "Requirement: user logged on at 10 PM; SoftDent SQLite + Sensei Reference present."
Write-Host "Env: .env.vyne.local Wichita password; --verify drives Trellis UI."
Write-Host "APScheduler job nr2-trellis-verify also builds worklist when NR2 is running."
