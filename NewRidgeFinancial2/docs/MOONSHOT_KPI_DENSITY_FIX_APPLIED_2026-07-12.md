# Moonshot KPI Density Fix — APPLIED

**Date:** 2026-07-12  
**Consult:** `MOONSHOT_KPI_DENSITY_FIX_CONSULT_2026-07-12.md`  
**Build:** **hal-10562**  
**Operator:** proceed  

## Approval checklist (operator)

- [x] KPI budget ≤4 standalone tiles above fold (parent pages)  
- [x] Tax planning isolation → `#taxes/planning`  
- [x] Empty KPI omit (never `$0` pad)  
- [x] SoftDent / QuickBooks / A/R / Office Manager vital strips (≤4 pills)  
- [x] Financial secondary ops packed into one micro-strip  

## What changed

| Area | Change |
|------|--------|
| `apex_compact_pages_pack.py` | `apply_kpi_density_contract`, `build_kpi_micro_strip`, empty omit + pending chip, `KPI_BUDGET_ABOVE_FOLD=4` |
| `apex_backend.py` | BUILD_ID **hal-10562**; Taxes cockpit slim; SoftDent/QB/AR/OM strips; Financial ops strip; density wired in `build_apex_widgets` |
| `apex_subpages_wave5_pack.py` | New `#taxes/planning` subpage with quarantined planning KPIs |
| `apex-core.js` | Hide omitted empty KPIs; `__nr2AssertKpiBudget(max=4)` |
| `apex-tokens.css` | `.apex-inst--kpi-omitted` hide rules |
| Assets / tests | Cache-bust + BUILD_ID asserts → hal-10562 |

## Validation

```text
python -m unittest test_compact_pages_pack test_kpi_density_hal10562 -v
→ OK (24 tests)
```

Browser (optional): on compact density, `__nr2AssertKpiBudget(4)` should return `{ ok: true, count: ≤4 }`.

## Honesty

- Empty ≠ `$0`  
- Planning estimates remain planning-only on `#taxes/planning` (CPA review)  
- Subpages may keep honest empty chips via `keepEmpty`  

## Rollback

Revert to **hal-10561** assets + prior `_taxes_widgets` / strip packing if needed.
