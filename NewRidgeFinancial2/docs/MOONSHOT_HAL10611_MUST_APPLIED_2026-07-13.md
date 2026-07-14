# Moonshot HAL-10611 MUST — APPLIED

**Source:** `MOONSHOT_MUST_PLAN_CODING_RESPONSE_2026-07-13.md`  
**Applied exactly as Moonshot specified (no Cursor-plan revisions).**

## Changes
- `nr2-build.json` → hal-10611
- `apex_backend.py` BUILD_ID + `apply_collapse_empty_all(..., page=pid)`
- `site/apex-core.js` ASSET_V → hal-10611
- `browser_app.py` `_port_available` + port-aware `ensure_singleton(host, port)` after bind_host resolve
- `apex_compact_pages_pack.py` financial `status=="empty"` omit with Moonshot exempt set

## Not applied (Moonshot out of scope)
- SoftDent A/R invent scheduler / desktop OPS remains operator action
