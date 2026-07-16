# OM Mon–Thu Patient List — APPLIED (Optical 2A)

**Date:** 2026-07-16  
**Consult:** `MOONSHOT_OM_MON_THU_PATIENT_LIST_PLACE_2026-07-16.md`  
**Operator:** approve → proceed with Optical OM (2A only); then **continue** for SHOULD/NICE

## Shipped

| Item | Where |
|------|--------|
| Mon–Thu schedule section | `site/nr2-optical-page-office-manager.html` (`#om-weekly-schedule`) |
| Fetch + render (PHI initials/hash) | `site/nr2-optical-page-office-manager.js` → `GET /api/softdent/appointments-range?days=4` |
| Grid styles + today highlight | `site/nr2-optical-theme.css` (`.om-weekly`, `.wk-days-grid`) |
| **SHOULD** Provider filter | `#wk-provider` → `?provider=` on appointments-range |
| **NICE** Click → mini dossier | `#wk-dossier` + `GET /api/apex/patient-dossier-mini/{id}` + audit POST |
| **NICE** Print stylesheet | `@media print` hides OPS chrome; keeps Mon–Thu grid |

## Honesty

- SoftDent read-only; reuses existing `appointments_range_snapshot`
- Board shows initials + short hash only (no full name)
- Time column stays `—` (no SoftDent appt time)
- Empty days show honest empty message
- Mini dossier: carrier / open claims / last visit / notes flag; account $ = unavailable when unknown

## How to try

1. Open Office Manager optical page (hard-refresh).
2. Confirm **This Week · Mon – Thu** grid under the OPS strip.
3. Optional: filter by **Provider**, click a row for mini dossier, **Refresh**, or Print.
