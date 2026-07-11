# Moonshot HAL Collections Empty Inventory — Applied

**Date:** 2026-07-11  
**Build:** **hal-10464**  
**Consult:** `MOONSHOT_HAL_COLLECTIONS_EMPTY_CONSULT_2026-07-11.md`  
**Status:** Applied after operator **approve/proceed** (Deltas **A + B**; Delta C prior-period fallback deferred)

## What shipped

### Delta A — Census skip bug
`summarize_widget_census` now excludes widgets with `type == "hal-chat"` (not only `id` prefix `hal-chat*`). Ask HAL (`id: hal-ask`) no longer counts as “with data.”

### Delta B — Actionable Collections pending
When inventory/census finds Collections empty with pending/missing hint:
- Reply appends operational fix text (daysheet / Register for a Period / Sync — not $0)
- Board actions: warn banner → navigate SoftDent → focus/highlight `sd-collections`
- HAL mosaic Collections hint clarifies the import path

## Files

| File | Change |
|------|--------|
| `apex_backend.py` | Census skip, helpers, inventory/census replies + board actions, BUILD_ID |
| `test_hal_collections_census.py` | Unit tests (4) |
| `nr2-build.json` / site mirror / `index.html` / `sw.js` / `apex-core.js` | **hal-10464** |

## Not applied

- Delta C prior-period Collections fallback (honesty / UX defer)

## Validate

1. Restart Start Program  
2. On HAL ask inventory / empty widgets  
3. Expect Ask HAL **not** in Showing; Collections empty with Fix line; SoftDent Collections focus  
4. Ops: import daysheet + Sync to populate Collections  
