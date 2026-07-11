# Phase X0–X2 Applied — Burn-in Ops Runbooks (Moonshot REAUDIT6)

**Date:** 2026-07-11  
**Build:** hal-10493  
**Consult:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT6_2026-07-11.md`  
**Status:** X0–X2 runbooks shipped — **flags remain OFF until operator executes scripts**

## Verdict (from REAUDIT6)

Sections 1–2 of the original Program Manager request are **architecturally complete** at hal-10492+.  
Remaining work is operational enablement only (no new feature packs).

## Shipped artifacts

| Phase | Artifact | Purpose |
|-------|----------|---------|
| **X0** | `scripts/nr2_burnin_enable_flags.ps1` | Flip burn-in env flags ON (`setx`) |
| **X0** | `scripts/nr2_burnin_disable_flags.ps1` | Rollback flags to OFF |
| **X1** | `scripts/nr2_register_scheduled_tasks.ps1` | Register Import Cron + Monthly Audit tasks |
| **X1** | `scripts/nr2_unregister_scheduled_tasks.ps1` | Remove Task Scheduler entries |
| **X2** | `scripts/validate_nr2_burnin.py` | Post-enablement pytest + dry-run crons |
| **Doc** | this file | Operator checklist |

## X0 — Flag flip (opt-in)

Run in an elevated PowerShell **after** SoftDent nightly export SOP is ready:

```powershell
cd C:\NewRidgeFamilyFinancial
.\scripts\nr2_burnin_enable_flags.ps1
# opens a NEW shell to see setx values:
.\scripts\nr2_burnin_enable_flags.ps1 -Verify
```

Flags set:

| Flag | Value | Role |
|------|-------|------|
| `NR2_IMPORT_CRON` | `1` | W1 import automation |
| `NR2_IMPORT_CRON_SEC` | `300` | 5-minute poll interval |
| `NR2_AUDIT_CRON` | `1` | V0 monthly deep audit |
| `NR2_AI_TELEMETRY` | `1` | V0 lane health |
| `NR2_DATA_FRESHNESS` | `1` | V0 freshness chips |
| `NR2_EXPLAIN_CACHE` | `1` | V2 30B explain LRU |

**Note:** `setx` updates the user environment for **future** processes. Restart NR2 / Task Scheduler tasks after enabling.

Rollback:

```powershell
.\scripts\nr2_burnin_disable_flags.ps1
```

## X1 — Task Scheduler (opt-in, admin)

```powershell
cd C:\NewRidgeFamilyFinancial
# Review paths first
.\scripts\nr2_register_scheduled_tasks.ps1 -WhatIf
# Register (may need Run as Administrator)
.\scripts\nr2_register_scheduled_tasks.ps1
```

| Task | Schedule | Script |
|------|----------|--------|
| `NR2_Import_Cron` | every 5 minutes | `scripts/run_nr2_import_cron.py` |
| `NR2_Monthly_Audit` | 1st of month 06:00 | `scripts/run_nr2_scheduled_audit.py` |

Unregister:

```powershell
.\scripts\nr2_unregister_scheduled_tasks.ps1
```

## X2 — Validation

```powershell
cd C:\NewRidgeFamilyFinancial
python scripts/validate_nr2_burnin.py
# or force cron dry-runs even if flags still OFF:
python scripts/validate_nr2_burnin.py --force-cron
```

## Honesty / safety

- Scripts **do not** SoftDent write-back
- Import cron remains DQ reject-only; quarantine UI unchanged
- Empty ≠ $0; gap codes preserved
- Do not enable `NR2_IMPORT_CRON` until SoftDent/QB export drop discipline is documented

## Future (vendor — out of scope)

- QuickBooks Online OAuth API  
- SoftDent live API / ERA posting write-back
