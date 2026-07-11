# HAL Patient Full Summary / Mega-Dossier — Applied

**Date:** 2026-07-11  
**Build:** **hal-10495**  
**Consult:** `MOONSHOT_HAL_PATIENT_FULL_SUMMARY_CONSULT_2026-07-11.md`  
**Status:** All MUST / SHOULD / NICE items applied after operator “proceed as moonshot ai directed without deviation”

## Shipped checklist

| Priority | Item | Status | Where |
|----------|------|--------|-------|
| **MUST** | `build_patient_dossier` + `empty≠$0` (`_safe_money`) | Done | `patient_dossier.py` |
| **MUST** | `GET /api/apex/patient-dossier/{id}` + RBAC | Done | `apex_backend.py` · capability `read_patient_dossier` (maps consult `hal:patient-dossier:read`) |
| **MUST** | `summarize_patient_dossier` HAL tool · local 24B | Done | `site/hal-agent.js` → bridge → `?summarize=1` → `hal-local:24b` with deterministic fallback |
| **MUST** | Audit `hal_patient_query_audit` | Done | `hal_patient_audit.py` (+ JSONL mirror via `nr2_audit_log`) |
| **SHOULD** | `DOSSIER_SUMMARY_PROMPT` | Done | `patient_dossier_prompts.py` |
| **SHOULD** | `DesktopBridge.fetchPatientDossier` | Done | `site/desktop-bridge.js` |
| **SHOULD** | Unit tests empty≠$0 | Done | `test_patient_dossier.py` |
| **NICE** | OM widget `patient-dossier-card` | Done | `apex_missing_widgets_pack.py` + `apex-core.js` renderer |
| **NICE** | 5-minute dossier cache | Done | `patient_dossier._CACHE` |
| **NICE** | PDF export | Deferred | Not required for core path; print via existing widget print |

## Honesty / invariants

- SoftDent **READ-ONLY** (SELECT only in dossier builders)
- Empty / null / 0 money → **`unknown`**, never `$0.00`
- PHI: widgets/summary use **hash/initials**; full name not echoed in markdown summary
- Local AI: `hal-local:24b` via gateway; cloud not used for dossier summarize
- Claims join uses **`patient_name`** (real schema — `sd_claims` has no `patient_id`)
- Clinical notes via `nr2_clinical_bridge` (no invented `clinical_note_imports` table)

## Schema gaps (documented, not invented)

- `sd_appointments` has **no appt_time** → time shown as `—`
- `sd_patients` has **no DOB/SSN/first_name/last_name** → `patient_name` only
- No per-patient SoftDent “active treatment plan” table → estimates from `lookup_treatment_estimate` on recent ADAs × payer hint
- Account balance not in extract → `"unavailable"` (never `$0`)

## How to try

1. Open Office Manager (or HAL chat).
2. Ask HAL: **`Summarize patient P100`** (use a real SoftDent `patient_id` from extract)  
   or: **`Summarize patient A3F9`** after selecting a hash on the Mon–Thu list.
3. Staff with `office_manager` / `dentist` / `admin` roles have `read_patient_dossier`.

## Files

- `patient_dossier.py`, `patient_dossier_prompts.py`, `hal_patient_audit.py` (new)
- `apex_backend.py` (route + BUILD_ID)
- `nr2_rbac.py` (`read_patient_dossier`)
- `site/hal-agent.js`, `site/desktop-bridge.js`, `site/apex-core.js`
- `apex_missing_widgets_pack.py` (dossier card)
- `test_patient_dossier.py`
- `nr2-build.json` / `site/nr2-build.json` / `site/sw.js` / `site/index.html` → **hal-10495**

## Tests

`python -m pytest NewRidgeFinancial2/test_patient_dossier.py NewRidgeFinancial2/test_om_tx_claims_schedule.py -q` → **22 passed**
