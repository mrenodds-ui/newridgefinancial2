# Phase X0 — Enable NR2 burn-in environment flags (Moonshot REAUDIT6).
# Opt-in: does NOT change the current process env; setx applies to future shells/tasks.
# Requires: SoftDent nightly export SOP ready. Restart NR2 after running.
#
# Usage:
#   .\scripts\nr2_burnin_enable_flags.ps1
#   .\scripts\nr2_burnin_enable_flags.ps1 -Verify
#   .\scripts\nr2_burnin_enable_flags.ps1 -WhatIf

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$Verify
)

$ErrorActionPreference = "Stop"

$flags = [ordered]@{
    "NR2_IMPORT_CRON"     = "1"
    "NR2_IMPORT_CRON_SEC" = "300"
    "NR2_AUDIT_CRON"      = "1"
    "NR2_AI_TELEMETRY"    = "1"
    "NR2_DATA_FRESHNESS"  = "1"
    "NR2_EXPLAIN_CACHE"   = "1"
}

if ($Verify) {
    Write-Host "Burn-in flag verification (User environment):"
    foreach ($name in $flags.Keys) {
        $val = [Environment]::GetEnvironmentVariable($name, "User")
        Write-Host ("  {0}={1}" -f $name, $(if ($null -eq $val -or $val -eq "") { "(unset)" } else { $val }))
    }
    exit 0
}

Write-Host "Enabling NR2 burn-in flags via setx (User scope)..."
foreach ($name in $flags.Keys) {
    $value = $flags[$name]
    if ($PSCmdlet.ShouldProcess($name, "setx $name $value")) {
        & setx.exe $name $value | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "setx failed for $name (exit $LASTEXITCODE)"
        }
        Write-Host "  setx $name=$value"
    }
}

Write-Host ""
Write-Host "Done. Open a NEW shell (and restart NR2 / scheduled tasks) so processes pick up setx values."
Write-Host "Validate with:  .\scripts\nr2_burnin_enable_flags.ps1 -Verify"
Write-Host "Rollback with:  .\scripts\nr2_burnin_disable_flags.ps1"
