# Moonshot AI — OM Schedule Enrich (name / time / ADA / click summary)

**Date:** 2026-07-16
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_om_schedule_enrich_consult.py`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> ask moonshot ai how to make the scheduled patient in the office manager's page have more information on the page with patient name, time of appt, adding ada codes for that appointment and the ability to click on that patient in the list and bring up a summary

---

# Verdict
Extend the SoftDent ODBC extract to capture `appt_time`, enrich `appointments_range_snapshot` with a same‑day ADA‑procedure join, upgrade the OM row renderer to display honest initials‑plus‑hash (or policy‑approved full name) with real procedure hints, and deepen the click‑through to an auto‑summarized HAL dossier.

## 0. Operator Intent (verbatim)
> ask moonshot ai how to make the scheduled patient in the office manager's page have more information on the page with patient name, time of appt, adding ada codes for that appointment and the ability to click on that patient in the list and bring up a summary

## 1. Recommended PACKAGE
**Package ID:** NR2‑12044‑OM‑SCHEDULE‑ENRICH  
**Why now:** The OM board is the highest‑traffic clinical‑financial touchpoint; enriching it reduces clicks to the dossier while keeping the “empty ≠ $0” contract intact.  
**Effort:** Medium (2–3 days). Requires ODBC schema extension, SQL join logic, and DOM render update. No new React/TSX components—extends existing vanilla JS stack.

**REAL files to touch:**
- `softdent_odbc_extract.py` – add `appt_time` column mapping from SoftDent.Appointments table.
- `nr2_softdent_daily.py` – modify `appointments_range_snapshot` to:
  - LEFT JOIN `sd_procedures` ON `patient_id` + `proc_date = appt_date` (same‑day ADA rollup).
  - Aggregate ADA codes as `STRING_AGG(DISTINCT ada_code, ', ')` into `procedureHint`.
- `nr2-optical-page-office-manager.js` – update row template:
  - Replace `time: "—"` with conditional `HH:MM` or `"—"` (honest fallback).
  - Replace `procedureHint: "—"` with rolled‑up ADA string or `"—"`.
  - Add `data-patient-id` attribute for click handling.
- `nr2-optical-page-office-manager.html` – add `<template id="om-row-enriched">` slot for ADA badges.
- `om_patient_dossier.py` (or `patient_dossier.py`) – ensure mini‑dossier endpoint accepts `?autoSummarize=true` to trigger HAL on open.
- `nr2-optical-theme.css` – utility classes for `.ada-badge` and `.time-missing` tooltip styling.

**Validation gate:**
1. ODBC extract succeeds with new `appt_time` column without breaking nightly import (red‑laser check).
2. Same‑day ADA join returns ≤1 row per appointment (distinct aggregation verified).
3. OM board renders `"—"` for time with tooltip “Time not yet extracted” until gate 1 passes (honest UI).

## 2. Data honesty plan
| Request | Current State | Availability | Implementation |
|---------|---------------|--------------|----------------|
| **Patient Name** | `initials` only (e.g., “SP—”) | `sd_patients.patient_name` exists; policy blocks display | Keep initials on public board; expose full name **only** inside RBAC‑gated dossier click‑through unless Office Manager attests to PHI exposure risk. |
| **Appointment Time** | Hard‑coded `"—"` | **Not in cache**; `sd_appointments` lacks `appt_time` | **Must extend** `softdent_odbc_extract.py` to pull `Appointments.ApptTime`. Until shipped, UI shows `"—"` with `title="Pending ODBC schema update"`. Empty ≠ “00:00”. |
| **ADA Codes** | `"—"` | `sd_procedures.ada_code` + `proc_date` joinable | Same‑day join on `patient_id` + date. Aggregate to comma‑separated list (e.g., “D0120, D0220”). If no procedures, remain `"—"` (empty, not $0). |

**Blocked/Out of scope:** Real‑time SoftDent write‑back (forbidden); inventing times when column is null; displaying $0.00 when production field is missing.

## 3. Click → summary UX
**Reuse & deepen the existing mini‑dossier:**
- **Row click:** Keep current listener that slides open the side panel (`#miniDossierPanel`).
- **Enhancement:** On panel open, auto‑fire HAL summarize using existing `/api/hal/summarize` endpoint with `patientContext + dossierSnapshot`.
- **New affordance:** Add “Open Full Dossier” button inside mini‑panel that routes to `/patient-dossier-full/{id}` for OM users who need clinical notes + estimates + attest review.
- **Loading state:** Show skeleton screen while HAL summary streams; fallback to static dossier if HAL hub unreachable.

Alternative rejected: Full‑page modal (breaks OM workflow of quick scanning).

## 4. PHI / RBAC note
**Current policy:** Optical board shows `hash + initials` only (e.g., “#a1b2c3 · SP—”) to avoid shoulder‑surfing in open‑plan office.

**To expose full name on the board:**
- Requires `office_manager` role attestation flag `phiExposureAccepted=true` in user profile.
- If flag missing, render:
  - **Public:** initials + hash + ADA codes (clinical context without PII).
  - **Private (click):** full name revealed only inside RBAC‑gated dossier panel.

**Recommendation:** Implement the “enriched initials” path first (add ADA codes, keep initials), then gate full‑name display behind explicit OM attestation to avoid accidental HIPAA exposure on hallway monitors.

## 5. Runner‑ups
1. **Procedure‑Only Quick Win (NR2‑12044‑MINI):** Skip the ODBC time‑column work; only add the same‑day ADA join. Delays value by 1 day but leaves time as `"—"` until IT schedules ODBC change.
2. **Desktop GUI Bridge (NR2‑12044‑LIVE):** Instead of extending ODBC, build a SoftDent Desktop GUI “lane” that scrapes the live Appointment Book via COM/ODBC direct query when OM clicks “Refresh”. Higher latency, no cache, but gets real time immediately.
3. **Weekly HAL Digest Column:** Add a small “HAL” icon in the row that expands a tooltip summary instead of clicking into dossier. Rejected: adds cognitive load without satisfying the “click for summary” requirement.

## 6. What NOT to redo
- **Do not** rebuild the Mon‑Thu grid as a React calendar; keep the existing lightweight HTML table for performance.
- **Do not** invent synthetic times (e.g., defaulting to “09:00 AM”) when `appt_time` is missing.
- **Do not** bypass the existing `patient_dossier_mini` API; extend it with optional HAL injection rather than creating a parallel endpoint.
- **Do not** display `$0.00` for production when `sd_procedures.production` is null; preserve the `emptyNotZero` contract.

## 7. Acceptance criteria
- [ ] `softdent_odbc_extract.py` maps `Appointments.ApptTime` → `sd_appointments.appt_time` without breaking nightly import.
- [ ] `nr2_softdent_daily.py` returns `procedureHint` containing comma‑separated ADA codes for same‑day procedures; `"—"` if none.
- [ ] OM board renders `time` as `HH:MM` (12‑hour with AM/PM) when available; shows `"—"` with tooltip when not.
- [ ] OM board renders `initials` (or full name if PHI attestation enabled) + `patientHash`.
- [ ] Clicking any row opens mini‑dossier with HAL auto‑summarize pre‑loaded.
- [ ] No `$0` values appear for missing production; nulls render as `"—"`.
- [ ] Privacy: Full names never appear on board unless `phiExposureAccepted` flag is true in user session.

## 8. Executive Summary (5 bullets)
- **Schema Extension Required:** Real appointment times are absent from the current ODBC cache; we must extend `softdent_odbc_extract.py` to pull `appt_time` honestly rather than fabricating timestamps.
- **Same‑Day ADA Join:** ADA codes are available via `sd_procedures`; a left join on `patient_id` + date yields immediate procedure hints without waiting for SoftDent changes.
- **PHI Gate:** Full names on the public OM board require explicit Office Manager attestation; default implementation keeps initials‑only on the board and reveals full identity only inside the secure dossier click‑through.
- **Reuse Existing Dossier:** The click‑to‑summarize request is satisfied by deepening the current mini‑dossier panel with HAL auto‑summarize, avoiding redundant UI rebuilds.
- **Empty ≠ $0:** All missing data (time, production, ADA) render as `"—"` or null; we never default to zero or midnight, preserving financial audit integrity.

## 9. Approval Checklist
- [ ] **Policy:** Office Manager reviews and approves PHI exposure risk for full names (or accepts initials‑only default).
- [ ] **IT/DBA:** SoftDent ODBC extract schedule can accommodate `appt_time` column addition without locking the production database during business hours.
- [ ] **QA:** Validate that same‑day ADA join does not duplicate appointments when multiple procedures exist (distinct aggregation).
- [ ] **HAL:** Confirm HAL hub token scope includes `autoSummarize` for dossier context.
- [ ] **RBAC:** Verify `read_patient_dossier` capability is enforced on the mini‑dossier endpoint before exposing enriched data.
