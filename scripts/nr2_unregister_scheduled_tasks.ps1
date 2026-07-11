# Phase X1 — Unregister NR2 Task Scheduler jobs (rollback).
#
# Usage:
#   .\scripts\nr2_unregister_scheduled_tasks.ps1
#   .\scripts\nr2_unregister_scheduled_tasks.ps1 -WhatIf

[CmdletBinding(SupportsShouldProcess = $true)]
param()

$ErrorActionPreference = "Continue"
$names = @("NR2_Import_Cron", "NR2_Monthly_Audit")

foreach ($name in $names) {
    if ($PSCmdlet.ShouldProcess($name, "Unregister-ScheduledTask")) {
        try {
            Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction Stop
            Write-Host "Removed $name"
        } catch {
            Write-Host "Skip $name ($($_.Exception.Message))"
        }
    }
}
