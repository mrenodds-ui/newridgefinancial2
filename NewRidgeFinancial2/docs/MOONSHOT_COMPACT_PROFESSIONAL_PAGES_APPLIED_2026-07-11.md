# Moonshot Compact Professional Pages — APPLIED

**Date:** 2026-07-11  
**Consult:** `MOONSHOT_COMPACT_PROFESSIONAL_PAGES_CONSULT_2026-07-11.md`  
**Plan:** `MOONSHOT_COMPACT_PAGES_DETAILED_PLAN_2026-07-11.md`  
**Validation:** `MOONSHOT_COMPACT_PAGES_PLAN_VALIDATION_2026-07-11.md` (CONDITIONAL APPROVE)  
**Build:** `hal-10550`  
**Operator:** proceed exactly as Moonshot directed  

## Exemptions chosen (validation blockers)

| Fork | Choice |
|------|--------|
| **HAL chat** | Sole `l` instrument after status strip |
| **Claims kanban** | Pipeline summary strip (`s`) on Overview + full workbench on `#claims/kanban` |

## Phases shipped

| Phase | Build intent | What |
|-------|--------------|------|
| **1 Motion kill** | 10510 | Removed infinite breathe; border-only hover; enter `translateY(4px)`; stagger max 3; ambient sweep/tilt off by default; glitch only with `.is-error`; reduced-motion expanded |
| **2 Empty collapse** | 10520 | `collapse_empty_large` skips loading/skeleton; global pass in `build_apex_widgets` |
| **3 Size/grid** | 10530 | Gap 6px, body 12px, mosaic col 160px; `normalize_first_viewport`; Financial dual-axis → `l`; HAL sole `l` |
| **4 Subpages** | 10540 | `#claims/kanban`, `#office-manager/operatory`; main Claims uses pipeline summary |
| **5 Polish** | 10550 | Compact/Comfortable density toggle (`localStorage`); `j`/`k` strip focus |

## Key files

- `site/apex-tokens.css`, `apex-chrome-flash.css`, `apex-bridge.css`, `apex-motion-helper.js`, `apex-core.js`, `index.html`
- `apex_compact_pages_pack.py` (new)
- `apex_financial_console_pack.py`, `apex_backend.py`, `apex_subpages_wave5_pack.py`
- `test_compact_pages_pack.py`
- `nr2-build.json` → `hal-10550`

## Honesty

- Empty ≠ $0; empty large instruments collapse to strips.
- Loading/skeleton widgets are not collapsed (no thrash).

## Validate

1. Hard-refresh `https://127.0.0.1:8765/` (schema **hal-10550**)
2. Widgets do not breathe/float; no ambient sweep
3. Claims Overview = pipeline counts; Kanban subnav opens full board
4. HAL = import strip then chat at `l`
5. Density button toggles Compact ↔ Comfortable
