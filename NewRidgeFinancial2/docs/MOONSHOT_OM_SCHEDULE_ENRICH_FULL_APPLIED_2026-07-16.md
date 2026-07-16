# OM Schedule Enrich — Full Package APPLIED

**Date:** 2026-07-16  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_OM_SCHEDULE_ENRICH_2026-07-16.md`  
**Operator:** continue with all

## Shipped in this pass

| Item | Status |
|------|--------|
| Sensei/ODBC `appt_time` upsert + never wipe known times | `softdent_odbc_extract._upsert_sd_appointment` |
| Sensei backfill after extract | `backfill_appt_times_from_sensei` in `extract_softdent_odbc` |
| Live DB | ~11k/11k rows already timed on analytics DB |
| Provider section headers + print ADA/time | OM JS + theme print CSS |
| **Next timed** hint + NEXT badge | `nextPatient` on appointments-range + OM UI |
| Preserve-time unit tests | `test_appt_time_preserve.py` |
| Trellis nightly | Already on main (`c7da9de`) — not redone |

## Honesty

- SoftDent READ-ONLY; empty ≠ $0; board = initials + hash  
- Missing time still renders `—` (never invents 09:00)  
- Restart NR2 browser if UI still shows all dashes (API code must reload)

## Validation

```text
appointments_range_snapshot → times like 07:00 / ADA lists / nextPatient
```
