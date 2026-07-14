# Moonshot demotion apply — first-viewport → #{page}/ops (hal-10612)

**Date:** 2026-07-13  
**Build:** `hal-10612`  
**Status:** Applied

## What shipped
- `partition_first_viewport` in `apex_compact_pages_pack.py` keeps page allowlists on Overview and adds a **More Ops** strip (`#{page}/ops`).
- Ops subpages registered for financial, claims, taxes, HAL, SoftDent, A/R, QuickBooks, office-manager.
- Subnav **Ops** (+ Taxes **Planning**) wired in `apex-core.js`.
- SoftDent `softdent-gold-csv-drop-ops` stays on SoftDent Overview (OPS Excel/Print Preview path).
- Empty surfaces stay empty — demotion never pads `$0`.

## Keep sets (Overview)
See `PAGE_FIRST_VIEW_KEEP` in `apex_compact_pages_pack.py`.
