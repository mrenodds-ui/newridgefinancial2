# Moonshot AI — Claims Pro Presentation PRIMARY DESIGN APPLIED

**Date:** 2026-07-10  
**Build:** **hal-10420**  
**Consult:** `MOONSHOT_CLAIMS_PRO_PRESENTATION_CONSULT_2026-07-10.md`  
**Operator:** “implement primary design” (Executive RCM Console / Option A)

## Layout (matches consult wireframe)

| Level | Widget | Notes |
|-------|--------|-------|
| 1 | Import Health (`size: strip`) | ~40px compact strip |
| 1 | Claims Command Strip (`size: strip`) | Total / Open / Denied / At Risk $ / ERA % — unified card |
| 2 | Aging Exposure (`xl`) + Critical Actions (`m`) | Paired row; click filters workbench; Sync action on critical |
| 3 | Claims Workbench | Dense **table** default (32px rows) + Kanban toggle; view preference persisted |
| 4 | Risk Trend + ERA Match Rate gauge | Two medium widgets |

## Density / honesty polish

- Patient as `Last, First` when parseable  
- Attachment ● / ○ / — (no invented counts)  
- Dollar exposure hidden when amounts not on import  
- Table capped at 50 rows with “showing N of M”  
- SoftDent read-only; no invented dollars / claim IDs  

## Files

- `apex_claims_narratives_pack.py` — exposure/strip/critical/ERA gauge/workbench  
- `apex_backend.py` — `_claims_widgets` primary layout + `BUILD_ID`  
- `site/apex-core.js` / `apex-bridge.css` / `index.html`  
- `nr2-build.json` → **hal-10420**

## Prior

- `hal-10410` dual table/kanban scaffold  
- This build completes primary design sizing + Level 4 ERA gauge + density polish  
