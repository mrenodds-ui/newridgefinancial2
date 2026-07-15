# Moonshot AI — What's Next After Optical Money-Beam Binding (CONSULT ONLY)

**Date:** 2026-07-15
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Status:** ok
**Repo root:** `C:\Users\mreno\newridgefamilyfinancial`
**Prior:** `2d195e5` optical SoftDent/QB money-beam bind
**Script:** `scripts/run_moonshot_whats_next_after_optical_beam_bind_consult.py`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Wire the period-close morning scheduler to automatically pull fresh SoftDent data (pull_softdent=True) now that HAL-driven export is consent-free, completing the hands-free daily close rhythm.

## 0. Operator Intent (verbatim)
next

## 1. Recommended NEXT (name, why now, effort, REAL files/ops, validation gate)
**Package:** Period-Close Scheduler SoftDent Auto-Pull  
**Why now:** The LIVE AUDIT confirms period-close OPS is functional (`status: completed`, `lastBeamHash: 887abf908c98136e`) and SoftDent export is now consent-free for HAL (build `nr2-12028-export-consent-teach`). However, the scheduler currently runs an "attest-only" close without pulling SoftDent automatically. Wiring the auto-pull completes the automation loop, ensuring tomorrow’s close captures fresh claims data without manual intervention.  
**Effort:** Small-Medium (2–3 hours) — scheduler argument pass-through, consent-gate bypass confirmation, JSONL verification.  
**REAL files/ops:**
- `C:\Users\mreno\newridgefamilyfinancial\NewRidgeFinancial2\nr2_scheduler.py` — modify `run_period_close` invocation to pass `pull_softdent=True` on the 08:30 morning tick; remove consent-gate check for HAL-initiated pulls  
- `C:\Users\mreno\newridgefamilyfinancial\NewRidgeFinancial2\daily_closeout.py` — ensure `run_period_close(auto=True, pull_softdent=True)` routes through the consent-free `softdent_export()` path (Excel/Print Preview only, no write-back)  
- `C:\Users\mreno\newridgefamilyfinancial\NewRidgeFinancial2\nr2_hal_gateway.py` — confirm `POST /api/period-close/run` accepts `pull_softdent` boolean and propagates to closeout runner  
- `C:\Users\mreno\newridgefamilyfinancial\app_data\nr2\ops\daily_close_log.jsonl` — operational verification that automated pulls log `softdentTotal` with `auto: true` and `actor: SCHEDULER`  
**Validation gate:**  
- Tomorrow 08:30 local time: scheduler triggers close, log shows `softdentTotal` updated to match live beams (`$7,714` current), `beamHash` changes from prior day, and HAL `/period-close-status` returns `completed` with `shadowStartedAt` timestamp and no `consentRequired` flags.

## 2. Why this beats the other candidates now
- **Beats SoftDent GUI export hardening (1):** Path hardening is defensive maintenance; the LIVE AUDIT shows current exports are succeeding (fresh syncs at 22:23). Auto-pull is offensive capability that utilizes the consent-free export now proven stable.  
- **Beats BlueNote stall alerts (2):** Alerts are reactive insurance; the current state shows green lasers and completed closes. Auto-pull prevents data staleness proactively rather than announcing it.  
- **Beats HAL Force Close (3):** Force Close is a circuit-breaker for failures; the system is in steady-state success (`laserClear: true`). Automating the happy path has higher ROI than hardening the failure path first.  
- **Beats Desk proof smoke (6):** Validation is implicit in the LIVE AUDIT (beams present, hashes match). The next logical step is operationalization (automation), not additional manual verification.

## 3. Runner-ups (2–3)
1. **SoftDent GUI Excel path hardening (aging/register/collections save reliability)** — Harden export directory resolution and file-handle cleanup for long-running GUI sessions; defer until auto-pull shows path instability in logs.  
2. **HAL Force Close optical control (OM / Pages Hub — laser-gated, JSONL attest)** — Add emergency manual close button to optical pages when lasers are red; keep as safety valve for when auto-pull encounters unrecoverable staleness.  
3. **Desk proof smoke: optical AR/QB pages + HAL chat cite identical beamHash** — Formal acceptance test verifying `nr2-optical-page-*.js` headlines and HAL gateway return the same `4d8c7ec2c7b4dc72` hash; schedule post-auto-pull validation.

## 4. What NOT to redo
- Money-beam binding (optical benches already cite `/api/hal/tools/money-beams` per 2d195e5)  
- Period-close attest logic (shadow loop already logging JSONL per 8972b8d)  
- SoftDent consent-free export doctrine (already teaching HAL per 263b26b)  
- Money honesty / empty ≠ $0 handling (already live)  
- BlueNote chrome filter (SideNotes retired per fc804b6)  
- Laser softGap unification (already applied)  
- LIVE chrome honesty on Tax/OM/Documents (already shipped per 29629c1)

## 5. Acceptance criteria
- [ ] `nr2_scheduler.py` morning tick (08:30) invokes close with `pull_softdent=True`  
- [ ] `daily_close_log.jsonl` shows new entry with `actor: SCHEDULER`, `auto: true`, `softdentTotal` populated, and `beamHash` matching live beams endpoint  
- [ ] No consent dialog or `consentRequired: true` in HAL response when scheduler initiates pull  
- [ ] SoftDent dataset age resets to 0 minutes after scheduled close (fresh sync)  
- [ ] `invalidRootExists` flag remains true but code paths never reference `C:\NewRidgeFamilyFinancial` (hygiene maintained)

## 6. Executive Summary (5 bullets)
- **Context:** Period-close OPS loop is live and beams are honest; SoftDent export is now consent-free for HAL.  
- **Gap:** Scheduler runs "attest-only" closes, leaving SoftDent data potentially stale until manual refresh.  
- **Solution:** Wire morning scheduler to invoke consent-free SoftDent export automatically (`pull_softdent=True`).  
- **Impact:** Fully automated daily close with guaranteed fresh SoftDent claims data; removes last manual step in shadow rhythm.  
- **Risk:** Low — leverages existing proven export paths; rollback via scheduler config flag.

## 7. Approval Checklist
- [ ] Operator confirms `newridgefamilyfinancial` (not `NewRidgeFamilyFinancial`) is active repo root  
- [ ] OM confirms 08:30 local time is acceptable window for automated SoftDent GUI interaction  
- [ ] HAL gateway token `5IfFGPQGC4Y9KGf-XiqfbErW3ocRbC-2yVah-Za76tM` valid for automated scheduled calls  
- [ ] Backup of `daily_close_log.jsonl` verified before first automated run  
- [ ] Stakeholder accepts that write-back remains forbidden (Excel/Print Preview only)
