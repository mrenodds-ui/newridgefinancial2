# OM Schedule Enrich track — COMPLETE

**Date:** 2026-07-16  
**Operator:** continue with all until done  
**Consult backlog:** `MOONSHOT_WHATS_NEXT_AFTER_DESK_SMOKE_THIS_PATIENT_2026-07-16.md`

## Backlog status

| # | Package | Status | Commit / note |
|---|---------|--------|----------------|
| 1 | Sensei/ODBC `appt_time` extract | **DONE** | `3992284` + `MOONSHOT_APPT_TIME_EXTRACT_APPLIED` |
| 2 | Trellis morning huddle OM panel | **DONE** | `3992284` / `137bc1a` + `MOONSHOT_TRELLIS_MORNING_HUDDLE_APPLIED` |
| 3 | OM board polish (provider groups, print, NEXT) | **DONE** | `17de5f9` |
| 4 | HAL this-patient harden (expired TTL hint) | **DONE** | this commit |
| 5 | Classic Apex 2B weekly widget | **SKIPPED** | Optional; optical OM track active |

## Operator-facing result

- Mon–Thu list: real times when Sensei/ODBC has them, ADA badges, click → name + summary  
- Next timed patient hint  
- Tomorrow Trellis insurance panel (hash/initials, verify status)  
- Desk smoke covers this-patient + Mon–Thu time coverage  
- SoftDent READ-ONLY · empty ≠ $0 · board PHI = initials + hash  

## Not in this track

- PushEngage moonshot docs (untracked, separate)  
- BlueNote watcher runtime pid/state files  

**Track closed.** Say “continue” for a fresh Moonshot what’s-next outside this backlog.
