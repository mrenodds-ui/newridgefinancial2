# Moonshot AI — What's Next After OM Schedule Track (CONSULT ONLY)

**Date:** 2026-07-16
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_whats_next_after_om_schedule_track_consult.py`
**Shipped:** `a4909f2` track complete
**Apply:** Operator said continue with all until done — Cursor may apply ordered backlog.

## Operator request (verbatim)

> continue with all until done

---

# Verdict
**PushEngage / flash-risk consult** is the immediate next package because the live audit explicitly flags `pushEngageDoc`, `pushEngageScript`, and `trackCompleteDoc` as untracked (`true`), blocking commit hygiene and risking loss of flash-risk logic before it enters the shadow system.

## 0. Operator Intent (verbatim)
continue with all until done

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Package:** PushEngage Flash-Risk Consult Track  
**Why now:**  
- `untrackedHint` in the live audit lists `pushEngageDoc`, `pushEngageScript`, and `trackCompleteDoc` as `true`, indicating completed but uncommitted work sitting in the working tree.  
- Untracked code is invisible to the shadow period-close process (`systemOfRecord: false`) and could be lost on the next clean build.  
- Flash-risk logic is a dependency for the later “Force Close” confidence script (risk scoring requires engagement telemetry).

**Effort:** Small–Medium (1–2 sessions)  
- Commit documentation, harden the engagement script against PHI leakage (initials+hash only), and close the track with a completion doc.

**REAL files (repo paths):**  
- `nr2/services/push_engagement.py` (flash-risk calculator)  
- `nr2/optical/hal_tools/flash_risk_service.js` (optical JS bridge)  
- `docs/runbooks/pushEngage_flash_risk.md` (untracked doc)  
- `docs/tracks/12043_pushEngage_completion.md` (track close doc)

**Validation gate:**  
- `git status` shows zero untracked files matching `*pushEngage*`.  
- `deskSmokeLast` returns `flashRiskEligible: true` (new capability flag).  
- Optical “SUMMARIZE” tool lists flash-risk tier without exposing PHI.

## 2. Ordered backlog AFTER #1 (2–4 items for continue-with-all)
1. **SoftDent GUI Morning-Bundle / Period-Close Shadow Hardening**  
   - *Why:* Live audit shows `appointmentsRange.hasData: true` but `apptTimeColumn: null`; the Sensei/ODBC back-end is done but the GUI bundle hasn’t mapped the preserved column. Harden the shadow period-close (`systemOfRecord: false`) against the SoftDent read-only constraint (empty ≠ $0).  
   - *Files:* `nr2/optical/widgets/morning_bundle.py`, `nr2/gui/softdent_bridge.js`, `nr2/period_close/shadow_validator.py`

2. **Desk Smoke Force-Close Enablement / Beam MATCH Morning Confidence Script**  
   - *Why:* `deskSmokeLast` is `GREEN`/`MATCH`, but `forceCloseAvailable: false`. Enable Force Close capability and script the morning confidence check that beams the MATCH state to the board.  
   - *Files:* `nr2/desk/force_close.py`, `nr2/beam/morning_confidence.py`, `nr2/scripts/morning_match.sh`

3. **Optical Hub Wire-Page Honesty / Money-Beam UX Polish**  
   - *Why:* Final UX pass to ensure “empty ≠ $0” is visually explicit and money-beam alignment lasers stay green during high-volume posting.  
   - *Files:* `nr2/optical/pages/wire_page.html`, `nr2/optical/css/money_beam.css`, `nr2/optical/js/honesty_widgets.js`

## 3. Why this beats the other candidates now
- **Untracked code is a liability:** The audit explicitly flags PushEngage artifacts as untracked; every other candidate is either already tracked or theoretical. Committing now prevents data loss.  
- **Desk smoke is already GREEN:** Rehearsing a green state is lower priority than securing uncommitted code. Force Close can wait until the GUI bundle is hardened (sequential dependency on appt_time GUI mapping).  
- **SoftDent GUI has a backend but no frontend:** The `apptTimeColumn: null` gap is real, but it depends on the PushEngage track being closed first to avoid merge conflicts in the optical layer.  
- **Trellis is excluded:** Despite the `HTTPError` in the audit, the operator constraint forbids redoing the Trellis huddle; therefore it is deferred indefinitely.

## 4. What NOT to redo
- **OM Mon–Thu enrich** (commit `a4909f2` / `137bc1a` / `3992284` / `17de5f9`): ADA logic, appt_time enrichment, click summary, NEXT hint, and provider groups are closed.  
- **Sensei/ODBC appt_time preserve + backfill:** ODBC layer already preserves `appt_time`; do not re-run backfill.  
- **Trellis tomorrow insurance OM panel:** Do not retry despite `HTTPError`; panel is considered complete per the closed track.  
- **HAL this-patient bind + expired TTL rebind hint:** TTL logic and rebind hints are live; do not refactor.  
- **Classic Apex 2B:** Explicitly skipped as optional in the closed track; remains out of scope.

## 5. Acceptance criteria
- **PushEngage Track:**  
  - All `*pushEngage*` files removed from `git status` untracked list.  
  - `flash_risk_service.js` passes PHI audit (initials+hash only, no full names).  
  - Desk smoke dashboard displays flash-risk tier (Low/Med/High) without hard-coding thresholds.  

- **SoftDent GUI Morning-Bundle (Backlog #2):**  
  - `appointmentsRange.apptTimeColumn` returns a valid column header (not `null`).  
  - Period-close shadow validator rejects any write-back attempt to SoftDent (read-only enforcement).  
  - Empty balance display explicitly renders as “—” or “Empty” (never “$0.00”).  

- **Desk Smoke Force Close (Backlog #3):**  
  - `deskSmokeLast.forceCloseAvailable` flips to `true`.  
  - Morning confidence script executes without ` beam MATCH` errors for 5 consecutive mornings.  

- **Optical Hub Polish (Backlog #4):**  
  - Wire-page displays “empty ≠ $0” tooltip on hover over zero-balance rows.  
  - Money-beam UX maintains `laserClear: true` under 100-row posting load.

## 6. Executive Summary (5 bullets)
- **Untracked PushEngage code blocks clean build state** and risks loss of flash-risk logic before it enters the shadow system.  
- **Live audit confirms GREEN desk state** but reveals `forceCloseAvailable: false`, requiring a follow-on enablement package after GUI hardening.  
- **Appointment time column mapping is incomplete** (`apptTimeColumn: null`) despite completed ODBC back-end work; GUI morning-bundle closes the loop.  
- **Period close is completed in shadow mode** (`systemOfRecord: false`); hardening the SoftDent read-only constraint prevents accidental write-back during the 30-day shadow period.  
- **Ordered backlog ensures sequential completion** without violating the “do not redo” constraint on the Trellis huddle or OM enrichment tracks.

## 7. Approval Checklist
- [ ] Operator confirms PushEngage files exist in working tree (`git status` shows untracked docs/scripts).  
- [ ] Risk accepted: Trellis `HTTPError` is intentionally deferred and **not** retried per closed-track constraint.  
- [ ] Business logic approved: Force Close capability may change financial controls (requires OM sign-off).  
- [ ] SoftDent write-back remains **forbidden**; all packages enforce read-only (no `INSERT`/`UPDATE`).  
- [ ] Backlog order approved for sequential execution (no parallel tracks until #1 is committed).
