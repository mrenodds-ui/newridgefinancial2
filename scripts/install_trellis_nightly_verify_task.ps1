# Install HAL nightly Trellis dental eligibility verify - Mon-Thu 10:10 PM interactive.
# Runs AFTER APScheduler 10:00 PM worklist build (job nr2-trellis-verify).
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

# Stagger to 10:10 PM so NR2 APScheduler can finish the SoftDent worklist at 10:00.
$action = New-ScheduledTaskAction `
    -Execute $Py `
    -Argument "`"$Script`" --force --verify" `
    -WorkingDirectory $RepoRoot

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday -At '10:10PM'

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

Write-Host "Installed '$TaskName' (Interactive / Mon-Thu 10:10 PM) for $CurrentUser."
Write-Host "APScheduler nr2-trellis-verify builds worklist at 10:00 PM; this task Verifies at 10:10 PM."
Write-Host "Requirement: user logged on; SoftDent SQLite + Sensei Reference + .env.vyne.local (Wichita)."
