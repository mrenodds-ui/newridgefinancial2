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
$nr2Root = Split-Path -Parent $scriptRoot
$warmScript = Join-Path $scriptRoot "Keep-HAL-Models-Warm.ps1"
. (Join-Path $nr2Root "scripts\Get-HiddenPowerShellLauncher.ps1")

$startupTaskLabel = if ($SystemBoot) { "New Ridge HAL Model Warmup (System Boot)" } else { "New Ridge HAL Model Warmup (Logon)" }
if ([string]::IsNullOrWhiteSpace($StartupTaskName)) {
    $StartupTaskName = $startupTaskLabel
}

if (-not (Test-Path $warmScript)) {
    throw "Warm script not found: $warmScript"
}

$psArgs = @()
if ($AllConfigured) { $psArgs += "-AllConfigured" }
if ($IncludeReasoningLanes) { $psArgs += "-IncludeReasoningLanes" }

$taskCommand = Get-HiddenPowerShellTaskCommand -ScriptPath $warmScript -ExtraArgs $psArgs

schtasks.exe /Create /TN $TaskName /SC MINUTE /MO $RepeatMinutes /TR $taskCommand /F
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create or update scheduled task '$TaskName'."
}

if ($SystemBoot) {
    schtasks.exe /Create /TN $StartupTaskName /SC ONSTART /TR $taskCommand /RU "SYSTEM" /RL HIGHEST /F
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create boot task '$StartupTaskName'. Run this script in an elevated (Administrator) PowerShell for -SystemBoot."
    }
    Write-Host "  '$StartupTaskName' runs at system startup (SYSTEM, pre-logon)."
} else {
    $startupDir = [Environment]::GetFolderPath("Startup")
    $launcherInfo = Get-HiddenPowerShellLauncher
    $oldCmd = Join-Path $startupDir "NewRidge-HAL-Model-Warmup.cmd"
    $oldVbs = Join-Path $startupDir "NewRidge-HAL-Model-Warmup.vbs"
    Remove-Item $oldCmd, $oldVbs -Force -ErrorAction SilentlyContinue

    # .pyw runs under pythonw with no console
    $startupPyw = Join-Path $startupDir "NewRidge-HAL-Model-Warmup.pyw"
    $extraLiteral = ($psArgs | ForEach-Object { ", " + ($_ | ConvertTo-Json) }) -join ""
    $pywBody = @"
import runpy, sys
sys.argv = [r"$($launcherInfo.Launcher)", r"$warmScript"$extraLiteral]
runpy.run_path(r"$($launcherInfo.Launcher)", run_name="__main__")
"@
    if ($launcherInfo.Kind -ne "pythonw") {
        # Fallback: tiny cmd that still tries to stay quiet
        $startupPyw = Join-Path $startupDir "NewRidge-HAL-Model-Warmup.cmd"
        $pywBody = "@echo off`r`n$taskCommand"
    }
    Set-Content -Path $startupPyw -Value $pywBody -Encoding ASCII
    Write-Host "  Logon warm start installed: $startupPyw"
}

Write-Host "Scheduled tasks registered (hidden):"
Write-Host "  '$TaskName' runs every $RepeatMinutes minute(s)."
Write-Host "Command: $taskCommand"
Write-Host ""
Write-Host "Run now:    schtasks /Run /TN `"$TaskName`""
Write-Host "Verify:     schtasks /Query /TN `"$TaskName`" /FO LIST"
Write-Host "Remove:     schtasks /Delete /TN `"$TaskName`" /F ; schtasks /Delete /TN `"$StartupTaskName`" /F"
Write-Host ""
Write-Host "For pre-logon boot start, re-run in an elevated PowerShell with -SystemBoot."
