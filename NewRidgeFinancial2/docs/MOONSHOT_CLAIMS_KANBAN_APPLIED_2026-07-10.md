# Claims Workbench Kanban (Mockup Parity Phase 1) — Applied

**Date:** 2026-07-10  
**Build:** **hal-10380**  
**Consult:** `MOONSHOT_CLAIMS_MOCKUP_PARITY_CONSULT_2026-07-10.md`  
**Status:** Option A Hybrid Phase 1 applied after operator “do it”

## What shipped

- Kept existing **30/60/90 claim-shelf** aging rows
- Added **Claims Workbench** read-only 5-column kanban:
  - Submitted · Pending Review · ERA Matched · Denied · Paid
- Claim cards: ID, patient, procedure (when on import), payer, amount (when on import), aging-risk badge, attachment/ERA chips when present
- **Pipeline stats** row: Pending $, At Risk, ERA Match % — honest empty when fields missing
- **Aging Risk** bars from Age/Days + denied status (not invented payer denial scores)
- Filters: All / High Risk / Unmatched / Missing Attachments (client-side)
- Click card → existing claim detail drawer
- HAL: focus workbench, filter high risk, focus widget IDs
- API: `GET /api/apex/claims-kanban`

## Honesty / limits

- **No drag write-back** (read-only SoftDent import)
- Never invents claim IDs, patients, dollars, ERA %, or denial codes
- Missing procedure/attachment/ERA fields show muted/hidden states
- Risk badge = aging/status proxy only

## Files

- `apex_claims_narratives_pack.py` — `build_status_columns`, kanban/header/risk widgets
- `apex_backend.py` — claims widgets + route + HAL board-actions
- `nr2_browser_security.py` — `/api/apex/claims-kanban`
- `site/apex-core.js` — render + wire + filter action
- `site/apex-bridge.css` — kanban/card/stats styles
- `site/index.html`, `nr2-build.json` — **hal-10380**
- `ci-fixtures/imports/softdent/softdent_claims_export.csv` — richer status/proc/ERA samples

## Not in Phase 1

- Dedicated full-page workbench chrome (Option B)
- SoftDent status write-back / drag-drop
- True ERA 835 match pipeline / attachment imaging integration
