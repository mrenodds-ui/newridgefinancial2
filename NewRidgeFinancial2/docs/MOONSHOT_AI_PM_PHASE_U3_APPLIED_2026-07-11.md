# Phase U3 Applied — Dashboard Layout Polish (Moonshot REAUDIT3 NICE)

**Date:** 2026-07-11  
**Build:** hal-10486  
**Consult:** `MOONSHOT_AI_PROGRAM_MANAGER_UPGRADE_REAUDIT3_2026-07-11.md`  
**Status:** U3 applied and validated

## Shipped

| Item | Detail |
|------|--------|
| Pack | `apex_dashboard_layout_pack.py` — per-page grid schema |
| Persist | `dashboard_layouts.json` + LocalStore key |
| Frontend | `site/nr2-dashboard-layout.js` + mosaic order in `apex-core.js` |
| CSS | `apex-mosaic--u3` denser flow (existing tokens) |
| APIs | `dashboard-layout` GET/POST + `dashboard-layout-reset` |
| Widget | `dashboard-layout-status` |
| Flag | `NR2_DASHBOARD_LAYOUT` default **ON** |
| Theme | **starship-bridge** (no rewrite / no invented dark skin) |

## Validation

```text
python -m pytest NewRidgeFinancial2/test_apex_dashboard_layout_u3.py -q
```

## Rollback

```text
set NR2_DASHBOARD_LAYOUT=0
```
