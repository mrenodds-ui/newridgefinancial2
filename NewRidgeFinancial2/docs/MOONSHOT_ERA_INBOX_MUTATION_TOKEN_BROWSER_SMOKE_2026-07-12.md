# Browser Smoke — ERA Inbox Mutation-Token / Refresh Inbox (hal-10574)

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_ERA_FIRST_DROP_OPS_2026-07-13.md`  
**Prior apply:** `MOONSHOT_ERA_INBOX_MUTATION_TOKEN_APPLIED_2026-07-13.md`  
**Operator:** proceed (browser smoke after 10574 ship)  
**Build:** **hal-10574**  
**URL:** `https://127.0.0.1:8765/?v=hal-10574-smoke2#softdent`

## Gates

| Gate | Result |
|------|--------|
| UI badge / `data-apex-version` = 10574 | **PASS** |
| `GET /api/apex/hal/era-inbox/status` → `mutationAuthRequired=true`, `buildId=hal-10574` | **PASS** |
| `GET /api/app-info` → session token (len 32) | **PASS** |
| `POST …/era-inbox/ingest` **without** token → **403** | **PASS** |
| `POST …/era-inbox/ingest` **with** `X-NR2-Session-Token` → **200**, empty honesty | **PASS** |
| SoftDent widgets warm → Collections Gap message `ERA_835_REQUIRED · 2026-07` | **PASS** |
| Gap tile shows **Refresh Inbox** button | **PASS** |
| Button click → `apexFetch` POST with session header → **200** | **PASS** |
| Response `empty=true`, `honesty=empty_not_zero`, `writeBack=false`, `chipLabel=Awaiting first 835 drop` | **PASS** |
| No SoftDent write-back / no Register re-export / no synthetic 835 | **PASS** |

## Instrumented UI click (CDP)

```text
POST /api/apex/hal/era-inbox/ingest
status=200
hasSessionHeader=true
body={ ok:true, empty:true, honesty:empty_not_zero, writeBack:false,
       chipLabel:"Awaiting first 835 drop", fileCount:0, buildId:hal-10574 }
```

## Notes

- First SoftDent load after restart can sit on `warming-bridge` stub until background widget fill completes (~tens of seconds). Smoke waited for warm cache (`18` widgets including `softdent-collections-gap`).
- Inbox remains empty — Refresh Inbox correctly stays awaiting (empty ≠ $0). Real payer 835 drop is still the OPS unblocker.

## Not done

- Third OPS procurement of real ERA-835 files  
- Collections Excel-temp / QB payroll/AP OPS  
