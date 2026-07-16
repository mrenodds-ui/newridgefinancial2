# OM Schedule Enrich (name / time / ADA / click summary) — APPLIED

**Date:** 2026-07-16  
**Consult:** `MOONSHOT_OM_SCHEDULE_ENRICH_CONSULT_2026-07-16.md`  
**Operator:** approve (spelled aprrove)

## Shipped

| Item | Where |
|------|--------|
| Same-day ADA join → `procedureHint` / `adaCodes` | `nr2_softdent_daily.appointments_range_snapshot` |
| Honest `appt_time` when column/data exists | same + Sensei/ODBC extract |
| Schema: `sd_appointments.appt_time` + ALTER migrate | `softdent_odbc_extract.ensure_sd_schema` |
| Sensei `Time` → `appt_time` | Sensei appointment ingest |
| Board: initials + hash + ADA badges + time | `nr2-optical-page-office-manager.js` + theme CSS |
| Dossier panel: full **Patient** name + appt ADA/time | mini-dossier rows |
| Click → SoftDent summary | `GET /api/hal/tools/patient-dossier-summary` into panel |
| Mini dossier returns `patientName` | `om_patient_dossier.get_patient_dossier_mini` |
| Tests | `test_om_schedule_enrich.py` |

## Honesty / PHI

- Board stays **initials · #hash** (hallway-safe). Full name only in RBAC dossier panel.
- Time stays **—** until SoftDent/Sensei extract fills `appt_time` — never invent `09:00`.
- ADA missing → **—** / empty badges — empty ≠ $0.
- SoftDent READ-ONLY throughout.

## After deploy

1. Restart NR2 browser/server.
2. Re-run SoftDent/Sensei extract so `appt_time` populates when available.
3. OM Mon–Thu: rows show ADA badges; click opens name + summary.
