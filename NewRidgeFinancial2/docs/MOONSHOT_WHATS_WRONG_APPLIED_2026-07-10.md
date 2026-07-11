# Moonshot What's Wrong — Applied (2026-07-10)

**Consult:** `MOONSHOT_WHATS_WRONG_CONSULT_2026-07-10.md`  
**Build:** hal-10441 / assets hal-10444

## Applied

| ID | Fix | Status |
|----|-----|--------|
| **DEF-003** | Deleted stale scheduled task `NewRidgeDashboardServersAutoStart` (path `C:\New folder\…`, last result -196608). NR2 Start Program task remains. | Done |
| **DEF-002** | HAL chat no longer wiped by page remount while thinking: `halChatBusy` forces silent refresh; `softRenderHalMain` keeps chat history. (Server already ThreadingMixIn.) | Done |
| **DEF-004** | Startup cache warm after import sync: `load_import_bundle` + `build_apex_widgets` for financial/hal/claims/taxes. | Done |
| **DEF-001** | Clearer empty strip for `revenue-composition` with SoftDent export paths. **Data still needed:** 2026-07 has production but `collectionsPending=true` — export SoftDent Collections/Daysheet for July. | Partial (ops) |

## Not applied (needs explicit phase approval / larger work)

- DEF-005 ERA 835 parser
- DEF-006 Claims kanban card actions
- DEF-007 Proactive HAL stale-import alerts

## Operator action still required

Export SoftDent **Collections/Daysheet** for **2026-07** into:
- `C:\SoftDent\softdentexportreports` or
- `C:\SoftDentReportExports`

Then Sync in NR2 so `revenue-composition` can populate.
