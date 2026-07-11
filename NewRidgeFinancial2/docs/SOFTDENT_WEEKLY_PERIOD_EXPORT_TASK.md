# SoftDent Weekly Period Export Task (IMP-002)

**Date:** 2026-07-10  
**Build:** hal-10380+ / **hal-10390**  
**Purpose:** Keep SoftDent Register / Daysheet periods current so Taxes C0 guidance and EBITDA stay unblocked.

## Operator checklist (manual until SoftDent CLI exists)

1. In SoftDent, export **Register** (Period MTD) and **Daysheet** for the current month.
2. Drop files into `C:\SoftDentReportExports\` (or your configured SoftDent report export folder).
3. In Apex HAL, run: **Refresh SoftDent period imports** (or Sync imports).
4. Confirm Taxes page **C0 import guidance** no longer lists the period as pending.

## Suggested Windows Task Scheduler

| Field | Value |
|---|---|
| Trigger | Weekly, Monday 7:00 AM (before morning huddle) |
| Action | Reminder only — SoftDent has no supported auto CLI for Register; operator exports, then Apex refresh |
| Optional script | After files land, call Apex `POST /api/apex/softdent/refresh-period` via local HTTPS session |

## HAL alerts

- **Import Health Monitor** warns when imports are ≥7 days stale or period gaps exist.
- Ask HAL: `Import health status` or `Morning briefing`.

## Honesty

- NR2 never invents period dollars. Missing periods show as pending until a real SoftDent export is ingested.
