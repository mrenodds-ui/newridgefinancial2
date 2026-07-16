# Moonshot AI — What's Next After Desk Smoke This-Patient (CONSULT ONLY)

**Date:** 2026-07-16
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_whats_next_after_desk_smoke_this_patient_consult.py`
**Shipped:** `daa7ba2`
**Apply:** Operator said continue with all — Cursor may apply #1 then backlog in order.

## Operator request (verbatim)

> continue with all

---

# Verdict
Wire the Sensei/ODBC layer to extract `appt_time` so the Mon–Thu OM board renders real HH:MM instead of "—".

## 0. Operator Intent (verbatim)
continue with all

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Package:** Sensei/ODBC `appt_time` extract (OM Board Time Fix)  
**Why now:** The LIVE AUDIT shows the Mon–Thu board UI is live (`apptTimeInDaily: true`, `monThuApptTimeOk: true`), yet every appointment displays "—" because the ODBC SELECT does not yet return the time column. This is a data-blocker that renders the board unusable for morning huddles and must be resolved before any grouping, filtering, or insurance worklist features can rely on appointment times.  
**Effort:** Small (1 dev-day). Single column addition to existing read-only query; no schema migration (already shipped in bc0c8ff).  
**REAL files:**
- `softdent_odbc_extract.py` – add `appt_time` (or `ApptTime`/`StartTime` per SoftDent schema) to the SELECT projection and row mapper.
- `nr2_softdent_daily.py` – ensure the daily ingest pipeline persists the new column to the office-hub dataset without coercion (NULL stays NULL).
- `desk_smoke.py` – extend the smoke test to assert that at least one non-null `appt_time` exists in the latest beam when SoftDent reports fresh data.  
**Validation gate:** Office Manager opens the Mon–Thu board and sees formatted times (e.g., "08:30", "14:00") next to patient initials; "—" appears only when the underlying SoftDent record truly lacks a time (empty ≠ "00:00").

## 2. Why this beats the other candidates now
- **Candidate #2 (Tomorrow-insurance worklist):** Requires accurate appointment times to sort the morning huddle; impossible while times are "—".  
- **Candidate #3 (Provider/operatory grouping):** Needs real timestamps to group by time blocks; polishing the UI is premature when the data is missing.  
- **Candidate #4 (Apex 2B widget):** Optional legacy feature with lower operational impact.  
- **Candidate #5 (LIVE AUDIT gap):** The audit explicitly flags `timeSamples: ["—"]` and `odbcMentionsApptTime: true`, confirming the gap is exactly the ODBC extraction, not a new unknown.

## 3. Ordered backlog AFTER #1 (2–4 items operator can "continue with all")
1. **SoftDent/Trellis tomorrow-insurance worklist / morning huddle surface** – surface appointments for tomorrow with insurance eligibility status (uses the now-working `appt_time` to sort chronologically).  
2. **Provider/operatory grouping + print polish on Mon–Thu board** – group by provider/operatory and enable print-friendly CSS now that times are populated.  
3. **Classic Apex 2B weekly widget (optional legacy only)** – port the legacy Apex 2B weekly summary view if staff request it during shadow phase.

## 4. What NOT to redo
- Desk smoke this-patient bind (`daa7ba2`)  
- HAL this-patient shortcut (`17ba77e`)  
- OM Mon–Thu ADA + appt_time UI/migrate (`f1e8ccb` / `bc0c8ff`) – the UI shell is shipped; only the data pipe is missing.  
- Trellis nightly verify harden (`c7da9de`)  
- Mini-dossier clinical/estimates, context bind, Ask HAL (patient track)  

## 5. Acceptance criteria
- [ ] `softdent_odbc_extract.py` SELECT statement includes the appointment time column (e.g., `SELECT ... ApptTime FROM Appointment ...`).  
- [ ] Row mapper returns `appt_time` as ISO string or `None` (never "—" or "00:00").  
- [ ] `nr2_softdent_daily.py` ingest completes without casting errors and stores the value in the existing `appt_time` field.  
- [ ] LIVE AUDIT `timeSamples` array contains at least one valid "HH:MM" value when SoftDent has scheduled appointments.  
- [ ] PHI protection maintained: patient names remain hashed/initials only on the OM board.  
- [ ] Empty handling: appointments with NULL times in SoftDent render as blank (not "$0" or "—").  

## 6. Executive Summary (5 bullets)
- **Unblock the board:** The Mon–Thu UI is live but showing "—"; wiring ODBC `appt_time` makes it operational for office managers.  
- **Read-only safety:** Pure SELECT against SoftDent; no write-back, no PHI exposure beyond existing initials hash.  
- **Enables downstream features:** Insurance worklist and provider grouping both depend on accurate timestamps.  
- **Low risk, high visibility:** Single column extraction using existing proven files (`softdent_odbc_extract.py`, `nr2_softdent_daily.py`).  
- **Validation is automatic:** Desk smoke already checks `monThuApptTimeOk`; extending it to verify non-null samples guarantees the fix.

## 7. Approval Checklist
- [ ] Confirm SoftDent table/column name for appointment start time (e.g., `Appointment.ApptTime`, `Schedule.StartTime`).  
- [ ] Verify `softdent_odbc_extract.py` ODBC driver permissions allow reading the time column.  
- [ ] Staging test: Run `nr2_softdent_daily.py` manually and confirm `appt_time` appears in the generated JSON beam.  
- [ ] UI spot-check: Office Manager views Mon–Thu board and sees "09:00" instead of "—" for a known 9:00 AM appointment.  
- [ ] Desk smoke assertion added to prevent regression (fail smoke if all times are null while appointment count > 0).
