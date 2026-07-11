# Phase X0 — Disable NR2 burn-in environment flags (rollback).
#
# Usage:
#   .\scripts\nr2_burnin_disable_flags.ps1
#   .\scripts\nr2_burnin_disable_flags.ps1 -WhatIf

[CmdletBinding(SupportsShouldProcess = $true)]
param()

$ErrorActionPreference = "Stop"

$flags = @(
    "NR2_IMPORT_CRON",
    "NR2_AUDIT_CRON",
    "NR2_AI_TELEMETRY",
    "NR2_DATA_FRESHNESS",
    "NR2_EXPLAIN_CACHE"
)

Write-Host "Disabling NR2 burn-in flags via setx (User scope)..."
foreach ($name in $flags) {
    if ($PSCmdlet.ShouldProcess($name, "setx $name 0")) {
        & setx.exe $name "0" | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "setx failed for $name (exit $LASTEXITCODE)"
        }
        Write-Host "  setx $name=0"
    }
}

# Interval can stay; harmless when cron is off
if ($PSCmdlet.ShouldProcess("NR2_IMPORT_CRON_SEC", "leave at 300 or clear")) {
    Write-Host "  (leaving NR2_IMPORT_CRON_SEC unchanged)"
}

Write-Host ""
Write-Host "Done. Restart NR2 / scheduled tasks. Optionally unregister tasks:"
Write-Host "  .\scripts\nr2_unregister_scheduled_tasks.ps1"
