# Moonshot AI — What's Next After Trellis Full Benefits (CONSULT ONLY)

**Date:** 2026-07-16
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_whats_next_after_trellis_benefits_consult.py`
**Closed:** Trellis ClearCoverage full benefits + HTML report (main); morning-bundle code harden (live still blocked)
**Apply:** Operator must say continue / approve before Cursor applies.

## Operator request (verbatim)

> next

---

# Verdict
Execute **Attended SoftDent morning Excel bundle re-run** immediately to clear the sole live blocker (aging/register/collections export failure), then surface the benefits HTML for staff once tonight’s Trellis batch populates the data.

## 0. Operator Intent (verbatim)
next

## 1. Recommended NEXT
**Name:** Attended SoftDent morning Excel bundle re-run  
**Why now:** `live.periodCloseStatus.morningBundle.ok` is `false` with `softdent_export_failed`; this is the only non-optional blocking item in the live audit. The code hardening (focus reclaim, F10 menus, AG*.XLS) is already applied, but Claim Management Chrome stole SoftDent focus during the unattended run, requiring an attended session to complete the aging → register → collections Excel capture.  
**Effort:** 1 attended session (15–20 min), operator-driven with HAL oversight.  
**REAL files under NewRidgeFinancial2/:**  
- Module `softdent_gui_export` (exists per audit)  
- Module `softdent_report_pull` (exists per audit)  
- Reference `daily_closeout` orchestrator (exists per audit)  
**Validation gate:** `live.periodCloseStatus.morningBundle.ok` flips to `true`, `failed` array empties, and `emptyNotZero` PHI compliance is confirmed (null vs. $0 distinction preserved).

## 2. Ordered backlog AFTER #1
1. **Surface full benefits HTML / OM-safe link for staff** – Once tonight’s 10:10 PM Trellis `--verify` populates benefits, staff need a PHI-safe (initials+hash) view of the ClearCoverage data without exposing dollar amounts on the huddle panel. Leverages existing `build_trellis_eligibility_report` module.  
2. **SoftDent desktop report-pull / HAL softdent-report-pull teach hardening** – Prevent recurrence of Chrome focus theft by teaching HAL the specific SoftDent menu states (Excel greyed vs. Print Preview) and focus-reclaim logic for future unattended runs.  
3. **Optional QB stale AP/payroll refresh** – Clear the optional dataset gaps (2409 min stale) noted in `importReadiness.datasetGaps`; non-blocking but improves financial close accuracy.

## 3. Why this beats the other candidates now
- **Candidate 2 (Benefits HTML):** Data backfill is already scheduled for tonight; surfacing can wait until the scrape completes, whereas the morning bundle is blocking daily closeout *now*.  
- **Candidate 3 (HAL teach):** Hardening prevents future failures, but the immediate failed state requires an attended recovery first (you cannot teach HAL on a broken run).  
- **Candidate 4 (QB refresh):** Explicitly marked `severity: optional` in the audit; morning bundle is the only `ok: false` blocking item.  
- **Candidate 5 (Apex widget):** Explicitly optional per constraints.

## 4. What NOT to redo
- OM schedule track logic  
- Trellis huddle panel (PHI-safe initials already implemented)  
- this-patient context builds  
- PushEngage embeds (avoid per BUILD_ID notes)  
- restart/Trellis HTTP proof  
- flip `forceCloseAvailable` on GREEN+MATCH (keep laser-gated)  
- Any SoftDent write-back (system is READ-ONLY)

## 5. Acceptance criteria
- [ ] Claim Management Chrome closed/backgrounded before run  
- [ ] SoftDent window foregrounded and confirmed active  
- [ ] Excel export path verified writable (AG*.XLS pattern)  
- [ ] Aging, Register, and Collections reports export successfully with `emptyNotZero` honored (empty cells remain empty, not $0)  
- [ ] `morningBundle.ok` returns `true` and `failed` array is empty in live audit  
- [ ] Output files stamped with board PHI initials+hash  
- [ ] No printer dialogs triggered (Excel or Print Preview only, Print Preview only if Excel greyed)

## 6. Executive Summary (5 bullets)
- **Sole Blocker:** The morning Excel bundle is the only live audit item failing (`softdent_export_failed`); all other systems are GREEN or optional.  
- **Attended Fix Required:** Code hardening is deployed, but focus theft by Claim Management Chrome necessitates an operator-attended run to reclaim SoftDent windows.  
- **Trellis on Autopilot:** Full benefits scrape and re-queue logic ships tonight at 10:10 PM via Task Scheduler; no dev intervention needed.  
- **Data Integrity:** SoftDent remains READ-ONLY; strict `emptyNotZero` compliance prevents false zeroing of uncollected amounts.  
- **Path to Close:** Unblock morning bundle → surface benefits HTML tomorrow → harden HAL for unattended stability → optional QB cleanup.

## 7. Approval Checklist
- [ ] Operator confirms Claim Management Chrome will be closed during the attended session  
- [ ] SoftDent desktop access confirmed (F10 menu navigation available)  
- [ ] Excel export directory permissions verified (AG*.XLS write access)  
- [ ] PHI hashing key available for initials+hash stamping  
- [ ] 20-minute attended window scheduled (aging → register → collections sequence)  
- [ ] Rollback plan: if export fails again, capture screenshot of SoftDent menu state for HAL teach hardening (Candidate 3)
