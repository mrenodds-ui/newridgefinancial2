# OM Mon–Thu Patients + HAL Patient Access — Applied

**Date:** 2026-07-11  
**Build:** **hal-10495**  
**Consult:** `MOONSHOT_OM_MON_THU_PATIENTS_HAL_CONSULT_2026-07-11.md`  
**Status:** Applied under the same operator “proceed without deviation” as the HAL dossier consult (same intent chain for OM + HAL patient access)

## Shipped checklist

| Priority | Item | Status | Where |
|----------|------|--------|-------|
| **MUST** | Mon–Thu list widget (PHI hashes) | Done | `appointments_range_snapshot` · `build_weekly_schedule_list` · `GET /api/softdent/appointments-range` |
| **MUST** | HAL patient context setter + audit | Done | `HalAgent.setOMPatientContext` · click hash on schedule · `hal_patient_audit` + `POST /api/audit/hal-patient-context` |
| **MUST** | Local-only enforcement | Done | Patient tools reject forced-cloud PHI path; summarization uses loopback 24B / deterministic |
| **SHOULD** | Patient dossier mini-widget | Done | `patient-dossier-mini` + `GET /api/apex/patient-dossier-mini/{id}` · `om_patient_dossier.py` |
| **SHOULD** | Treatment plan estimate surface | Done | `active-treatment-plans` widget (filled when dossier estimates present) |
| **SHOULD** | Claims review detail view | Done | `claim-review-detail` + `get_claims_review_detail` |
| **NICE** | Clinical notes viewer widget | Done | `clinical-notes-summary` |
| **NICE** | Provider filter on Mon–Thu list | Done | `?provider=` on appointments-range API |
| **NICE** | Print-friendly schedule PDF | Deferred | Use widget print; dedicated PDF not shipped |

## Honesty / invariants

- SoftDent **READ-ONLY** forever
- Empty days: honest empty message (not fake slots / not $0)
- Appointment **time = `—`** (schema has no `appt_time`)
- `sd_patients` join uses **`patient_name`** (not invented first/last columns)
- Treatment estimates: null / insufficient sample → **unknown**, never invented dollars
- Account balance → **unavailable** when not in SQLite

## How to try

1. Open **Office Manager**.
2. See **This Week's Schedule (Mon–Thu)** widget (prefetch loads `/api/softdent/appointments-range?start=<Monday>&days=4`).
3. Click a patient hash → sets HAL context (15 min TTL) + audit.
4. Ask HAL: **“about this patient”** or **“Summarize patient …”**.

## Files

- `nr2_softdent_daily.py` (`appointments_range_snapshot`, `monday_of_week_iso`)
- `nr2_http_server.py` (appointments-range route)
- `om_patient_dossier.py` (new)
- `apex_missing_widgets_pack.py` (weekly + dossier/tx/claims/notes widgets)
- `site/deferred-live-wire/nr2-softdent-daily.js`, `site/app.js` (prefetch)
- `site/apex-core.js` (schedule-list / action-list / dossier-card render + click wire)
- `site/hal-agent.js` (`set_patient_context`, `read_patient_summary`, context TTL)
- `hal_patient_audit.py` (`hal_patient_audit` table)

## Related

Also applied in the same build: `MOONSHOT_HAL_PATIENT_FULL_SUMMARY_APPLIED_2026-07-11.md` (mega-dossier API + HAL tool).

## Tests

Covered by `test_patient_dossier.py` (range snapshot, widgets, audit) + existing OM schedule gates → **22 passed** with dossier suite.
