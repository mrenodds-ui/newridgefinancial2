# Moonshot AI — What's Next After OM Schedule Enrich (CONSULT ONLY)

**Date:** 2026-07-16
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_whats_next_after_om_schedule_enrich_consult.py`
**Shipped:** `f1e8ccb`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> continue

---

# Verdict
Populate real appointment times end-to-end by wiring Sensei/ODBC time extraction into `sd_appointments.appt_time` and verifying OM UI renders live data instead of "—".

## 0. Operator Intent (verbatim)
continue

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** Sensei/ODBC `appt_time` Extract Hardening + OM UI Smoke Verification  
**Why now:**  
- f1e8ccb shipped the UI plumbing (honest appt_time rendering, ADA badges, click-summary), but the LIVE AUDIT shows `timeSamples` are 100% "—" (em dash), meaning the column exists but no data is flowing.  
- Without this, the "enriched" schedule is functionally incomplete; staff still cannot see when patients arrive.  
- Completes the same-day track started in f1e8ccb before moving to downstream workflows (insurance, checkout).  

**Effort:** Small (1–2 sessions). Focus on ODBC column mapping (`Time` or `ApptTime` in Sensei), extract transform logic, and idempotent upsert into `sd_appointments.appt_time`.

**REAL files (optical paths only):**  
- `nr2/io/extracts/softdent_appointments.py` (or equivalent ETL module handling `SELECT ... FROM Appointments` via pyodbc)  
- `nr2/pipeline/transforms/appointment_normalize.py` (maps raw Sensei `Time` → ISO `appt_time`)  
- `nr2/db/models/sd_appointments.py` (SQLAlchemy/DuckDB schema verifying `appt_time` is nullable timestamp)  
- Frontend: `OfficeManagerSchedule.vue` (or equivalent OM component already consuming `appt_time` via the enriched endpoint)

**Validation gate:**  
- LIVE AUDIT `appointmentsRange.timeSamples` shows ≥80% non-dash HH:MM strings for Mon–Thu rows after next extract cycle.  
- UI smoke: Clicking a row with a time reveals the same timestamp in the dossier panel SoftDent summary (consistency check).

## 2. Why this beats the other candidates now
- **Beats Candidate 3 (Desk smoke):** Audit already shows `deskSmokeLast.ok: true`, `status: GREEN`, `deskProof: MATCH`, and `patientAttestEligible: true`. The attest beam is proven; rehearsing it again delays fixing the empty data that users actually see.  
- **Beats Candidate 2 (Trellis insurance worklist):** Stale QuickBooks AP/Payroll are optional and do not block shadow operations. Appointment times are user-facing every morning.  
- **Beats Candidate 5 (Provider/operatory grouping):** Polishing layout on rows that display "—" for time is premature optimization. Data first, layout second.  
- **Beats Candidate 4 (Classic Apex widget):** Optical track (HAL patient summary) is active and unblocked; reverting to Classic Apex is a retreat, not a progression.

## 3. Runner-ups (2–3)
1. **Provider/operatory grouping + print layout polish** (Candidate 5) — valid immediate follow-up once times are live; improves scannability for front-desk staff.  
2. **SoftDent/Trellis tomorrow-insurance worklist hardening** (Candidate 2) — operational necessity for next-day eligibility checks, but not blocked by current data gaps.  
3. **HAL "next-patient" predictive beam** — leverage the now-proven patient attest flow to suggest which enriched-row patient should be checked in next; depends on live appt_time to sort chronologically.

## 4. What NOT to redo
- Mon–Thu list shell (rendering logic exists).  
- ADA join / `procedureHint` / `adaCodes` badge (already shipped).  
- Click-to-dossier summary + SoftDent summary panel (already shipped).  
- MATCH-gated patient attest review UI (already shipped, already green).  
- HAL this-patient shortcut from bound session context (already shipped).

## 5. Acceptance criteria
- [ ] Sensei ODBC extract explicitly selects the appointment time column (e.g., `Appointments.Time` or `Schedule.StartTime`) and maps it to `appt_time` in the staging schema.  
- [ ] `sd_appointments.appt_time` is populated for ≥90% of future-duture appointments (Mon–Thu) within 5 minutes of extract completion.  
- [ ] LIVE AUDIT `appointmentsRange.apptTimeColumn` changes from `null` to the column name/reference.  
- [ ] OM UI renders times in local office timezone (no "—" dashes) for rows where Sensei has a time.  
- [ ] Empty string or null in Sensei correctly renders as "—" (preserving the honest-empty contract), but never "$0".  
- [ ] No write-back to SoftDent (read-only constraint maintained).

## 6. Executive Summary (5 bullets)
- **Context:** f1e8ccb delivered the OM schedule enrich UI, but the data layer (`appt_time`) is still emitting dashes, leaving the feature half-complete.  
- **Risk:** Staff relying on the board for chair checks will see blank times, eroding trust in the shadow system during the critical 30-day shadow period.  
- **Action:** Harden the ODBC extract path to pull the time field from Sensei and hydrate `sd_appointments.appt_time`.  
- **Validation:** LIVE AUDIT will flip `timeSamples` from "—" to actual timestamps, confirming end-to-end integrity.  
- **Outcome:** Unlocks the true value of the Mon–Thu enriched view and prepares the data foundation for downstream checkout/beam workflows.

## 7. Approval Checklist
- [ ] Operator confirms Sensei/ODBC credentials can read the `Time` column in the `Appointments` table (or equivalent).  
- [ ] Confirm no PII leakage in `appt_time` logging (times alone are safe, but logs must not include patient names).  
- [ ] Staging environment shows non-dash times before main deploy.  
- [ ] Rollback plan: revert extract mapping to previous column set (dashes return, no crash).  
- [ ] Sign-off that this completes the f1e8ccb feature thread before opening new insurance/Trellis tracks.
