[CmdletBinding()]
param(
    [string]$TaskName = "New Ridge HAL Model Warmup",
    [string]$StartupTaskName = "",
    [int]$RepeatMinutes = 3,
    [switch]$AllConfigured,
    [switch]$IncludeReasoningLanes,
    [switch]$SystemBoot
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$warmScript = Join-Path $scriptRoot "Keep-HAL-Models-Warm.ps1"

$startupTaskLabel = if ($SystemBoot) { "New Ridge HAL Model Warmup (System Boot)" } else { "New Ridge HAL Model Warmup (Logon)" }
if ([string]::IsNullOrWhiteSpace($StartupTaskName)) {
    $StartupTaskName = $startupTaskLabel
}

if (-not (Test-Path $warmScript)) {
    throw "Warm script not found: $warmScript"
}

$arguments = @(
    "-NoProfile",
    "-WindowStyle Hidden",
    "-ExecutionPolicy Bypass",
    "-File `"$warmScript`""
)

if ($AllConfigured) {
    $arguments += "-AllConfigured"
}

if ($IncludeReasoningLanes) {
    $arguments += "-IncludeReasoningLanes"
}

$taskCommand = "powershell.exe " + ($arguments -join " ")

# Recurring task: re-warm the lane models on a short interval so the active
# set stays resident and recovers automatically after any eviction or restart.
# Runs in the current user session (no elevation required).
schtasks.exe /Create /TN $TaskName /SC MINUTE /MO $RepeatMinutes /TR $taskCommand /F
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create or update scheduled task '$TaskName'."
}

if ($SystemBoot) {
    # Pre-logon boot start. Requires an elevated (Administrator) shell because
    # it runs as SYSTEM at machine startup, whether or not anyone logs on.
    schtasks.exe /Create /TN $StartupTaskName /SC ONSTART /TR $taskCommand /RU "SYSTEM" /RL HIGHEST /F
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create boot task '$StartupTaskName'. Run this script in an elevated (Administrator) PowerShell for -SystemBoot."
    }
    Write-Host "  '$StartupTaskName' runs at system startup (SYSTEM, pre-logon)."
} else {
    # At-logon warm start via the current user's Startup folder. This runs when
    # the user logs on, needs no elevation, and is independent of the NR2 app.
    $startupDir = [Environment]::GetFolderPath("Startup")
    $launcher = Join-Path $startupDir "NewRidge-HAL-Model-Warmup.cmd"
    $launcherBody = "@echo off`r`nstart `"`" /min powershell.exe " + ($arguments -join " ")
    Set-Content -Path $launcher -Value $launcherBody -Encoding ASCII
    Write-Host "  Logon warm start installed: $launcher"
}

Write-Host "Scheduled tasks registered:"
Write-Host "  '$TaskName' runs every $RepeatMinutes minute(s)."
Write-Host "Command: $taskCommand"
Write-Host ""
Write-Host "Run now:    schtasks /Run /TN `"$TaskName`""
Write-Host "Verify:     schtasks /Query /TN `"$TaskName`" /FO LIST"
Write-Host "Remove:     schtasks /Delete /TN `"$TaskName`" /F ; schtasks /Delete /TN `"$StartupTaskName`" /F"
Write-Host ""
Write-Host "For pre-logon boot start, re-run in an elevated PowerShell with -SystemBoot."
