# Moonshot OM Tx / Claims / Schedule — APPLIED (hal-10494)

**Date:** 2026-07-11  
**Consult:** `MOONSHOT_OM_TX_CLAIMS_SCHEDULE_CONSULT_2026-07-11.md`  
**Directive:** proceed as Moonshot directed without deviation (MUST + SHOULD + NICE)

## Shipped

| Phase | Item | Implementation |
|-------|------|----------------|
| MUST OM-A0 | Daily OM appointments | `appointments_today_snapshot()` + `GET /api/softdent/appointments-today` |
| MUST | Operatory live fallback | `build_operatory_board(..., live_schedule=)` preferred over empty bundle |
| MUST | OM page prefetch | `NR2SoftdentDaily.prefetchTodayForOM()` on `page.id === "office-manager"` |
| MUST | Server-side inject | `append_office_manager_missing` calls live snapshot every OM widget build |
| SHOULD | Tx estimate HAL tool | `lookup_treatment_estimate` in `hal-agent.js` + `DesktopBridge.lookupTreatmentEstimate` → existing `/api/apex/treatment-planning/estimate` |
| SHOULD | Claims narrative OM queue | `build_claims_needing_narrative` widget |
| NICE | Recall booking hint | `bookingHint` when due > scheduled |
| NICE | Provider util 7d | `provider_utilization_last_7d` + `provider-util-7d` widget + API |

## Grounding notes (no deviation from SoftDent honesty)

- Real `sd_appointments` schema has **no** `operatory` / `appt_time` columns; reuse `_build_operatory_from_sd_appointments` (provider-as-chair).
- Patient display uses **4-char SHA256 hash** on live path (PHI-safe).
- SoftDent remains **read-only**; empty ≠ $0.

## Rollback

- Revert `site/app.js` OM prefetch block.
- Revert `append_office_manager_missing` live call (board falls back to bundle-only).
- `git checkout --` affected files on this commit.

## Validate

```powershell
cd NewRidgeFinancial2
python -m unittest test_om_tx_claims_schedule.py test_missing_widgets_coding_hal.py -v
```
