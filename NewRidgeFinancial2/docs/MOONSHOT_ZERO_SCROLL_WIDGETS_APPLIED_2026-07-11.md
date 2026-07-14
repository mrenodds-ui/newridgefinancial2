# Moonshot Zero-Scroll Widgets — APPLIED

**Date:** 2026-07-11  
**Consult:** `MOONSHOT_ZERO_SCROLL_WIDGETS_CONSULT_2026-07-11.md`  
**Budget:** `MOONSHOT_ZERO_SCROLL_PIXEL_BUDGET_2026-07-11.md`  
**Build:** **hal-10561**  
**Operator:** proceed and dont deviate from moonshot  

## Approval checklist (operator)

- [x] Claims Pipeline / Kanban → subpage (`#claims/kanban`); main = pipeline + Top 5  
- [x] HAL sole-l exemption removed; chat capped tile + Full Log strip  
- [x] 1920×1080 compact density validation standard  
- [x] Empty stays empty (no $0 padding)  
- [x] Compact density forced default; Comfortable may scroll  

## Phases

| Phase | Status | Deliverable |
|-------|--------|-------------|
| **A** Audit & Budget | Done | Pixel budget sheet |
| **B** Widget Contract | Done | `maxHeight` tiers 120/240/320; `rowCap` default 5; CSS overflow auto |
| **C** Spatial Reorg | Done | No main-page full kanban; HAL Full Log strip; height demotion of xl/full |
| **D** Validation | Done | Unit tests + `__nr2AssertZeroScroll` browser hook |

## Key changes

| Area | Change |
|------|--------|
| `apex_compact_pages_pack.py` | `apply_zero_scroll_contract`; HAL exemption removed; `claims_top_critical_widget` |
| `apex_backend.py` | BUILD_ID 10561; HAL chat `m`+320; contract in `build_apex_widgets`; Claims Top 5 |
| `apex-tokens.css` | Height tokens; compact page `overflow:hidden`; HAL chat no 100vh fill; gap 4px |
| `apex-bridge.css` | Instrument max-heights; financial/narr/claims tall mins removed |
| `apex-core.js` | Enforce `maxHeight`; rowCap 5; density default; `__nr2AssertZeroScroll` |

## Honesty

- Empty ≠ $0  
- Subpage Claims workbench may scroll internally (`internalScroll`)  

## Validate

1. Hard-refresh `https://127.0.0.1:8765/` (schema **hal-10561**)  
2. Compact density: no page scrollbar on Financial / Claims / HAL at 1920×1080  
3. Claims Overview = pipeline + Top 5; Kanban only on `#claims/kanban`  
4. HAL chat ≤320px; Full Log strip present  
5. Console: `__nr2AssertZeroScroll()` → `{ ok: true, … }`  
6. `python -m unittest test_compact_pages_pack -q`
