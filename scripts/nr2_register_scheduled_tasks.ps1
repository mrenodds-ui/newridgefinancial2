# Phase X1 — Register NR2 Task Scheduler jobs (Moonshot REAUDIT6).
# Prefer Run as Administrator. Resolves python + repo paths automatically.
#
# Usage:
#   .\scripts\nr2_register_scheduled_tasks.ps1 -WhatIf
#   .\scripts\nr2_register_scheduled_tasks.ps1

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$PythonExe = "",
    [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}
if (-not $PythonExe) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $PythonExe = $cmd.Source }
    else { $PythonExe = "python.exe" }
}

$importScript = Join-Path $RepoRoot "scripts\run_nr2_import_cron.py"
$auditScript = Join-Path $RepoRoot "scripts\run_nr2_scheduled_audit.py"

foreach ($p in @($importScript, $auditScript)) {
    if (-not (Test-Path -LiteralPath $p)) {
        throw "Missing script: $p"
    }
}

Write-Host "RepoRoot   : $RepoRoot"
Write-Host "PythonExe  : $PythonExe"
Write-Host "ImportCron : $importScript"
Write-Host "AuditCron  : $auditScript"

# --- Import cron: every 5 minutes ---
$importAction = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "`"$importScript`"" `
    -WorkingDirectory $RepoRoot

$importTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$importSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

if ($PSCmdlet.ShouldProcess("NR2_Import_Cron", "Register-ScheduledTask")) {
    Register-ScheduledTask `
        -TaskName "NR2_Import_Cron" `
        -Action $importAction `
        -Trigger $importTrigger `
        -Settings $importSettings `
        -Description "NR2 W1 DQ-gated import polling (Moonshot X1). Requires NR2_IMPORT_CRON=1." `
        -Force | Out-Null
    Write-Host "Registered NR2_Import_Cron (every 5 minutes)."
}

# --- Monthly audit: 1st of month 06:00 local ---
$auditAction = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "`"$auditScript`"" `
    -WorkingDirectory $RepoRoot

# -Monthly is available on Windows PowerShell; fall back to daily+script day check if needed
try {
    $auditTrigger = New-ScheduledTaskTrigger -Monthly -DaysOfMonth 1 -At "06:00"
} catch {
    Write-Warning "Monthly trigger unavailable; using daily 06:00 (script skips non-1st unless --force)."
    $auditTrigger = New-ScheduledTaskTrigger -Daily -At "06:00"
}

$auditSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

if ($PSCmdlet.ShouldProcess("NR2_Monthly_Audit", "Register-ScheduledTask")) {
    Register-ScheduledTask `
        -TaskName "NR2_Monthly_Audit" `
        -Action $auditAction `
        -Trigger $auditTrigger `
        -Settings $auditSettings `
        -Description "NR2 V0 monthly deep audit (Moonshot X1). Requires NR2_AUDIT_CRON=1." `
        -Force | Out-Null
    Write-Host "Registered NR2_Monthly_Audit (1st @ 06:00 or daily fallback)."
}

Write-Host ""
Write-Host "Ensure burn-in flags are ON before relying on tasks:"
Write-Host "  .\scripts\nr2_burnin_enable_flags.ps1"
Write-Host "  .\scripts\nr2_burnin_enable_flags.ps1 -Verify"
