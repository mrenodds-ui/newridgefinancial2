# Moonshot AI — What's Next After Restart Route Proof (CONSULT ONLY)

**Date:** 2026-07-16
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_whats_next_after_restart_proof_consult.py`
**Proved:** Trellis 200 + desk GREEN + apptTimeColumn
**Apply:** Operator said continue — Cursor may apply THE next package on real paths.

## Operator request (verbatim)

> continue

---

# Verdict
Execute **SoftDent GUI morning Excel bundle rehearsal** immediately to unblock the period-close hard close that is currently forced into attest-only fallback by failed aging/register/collections exports.

## 0. Operator Intent (verbatim)
continue

## 1. Recommended NEXT (name, why now, effort, REAL files under NewRidgeFinancial2/, validation gate)
**SoftDent GUI morning Excel bundle rehearsal** (`softdent_export_morning_bundle` shadow mode)  
- **Why now**: `periodCloseStatus.morningBundle.ok` is `false` with `softdent_export_failed` on aging, register, and collections. This forces the system into `attest_only` fallback and blocks hard period close despite desk smoke GREEN. The Trellis huddle and OM schedule are proven live; the next critical path bottleneck is the missing morning bundle.  
- **Effort**: 1–2 hours (shadow rehearsal + validation).  
- **REAL files**:  
  - `NewRidgeFinancial2/softdent_gui_export/` (Python optical automation for SoftDent desktop GUI)  
  - `NewRidgeFinancial2/hal_brain_tools_morning_bundle/` (parser/validator for empty≠$0 and PHI hashing)  
  - `NewRidgeFinancial2/daily_closeout/` (shadow orchestrator; period-close shadow gate)  
- **Validation gate**: `morningBundle.ok` flips `true` with three `.xlsx` files present in `period_close/incoming/`, `failed` array empty, and `emptyNotZero` explicitly handled (null vs $0 distinction preserved).

## 2. Ordered backlog AFTER #1 (2–4)
2. **SoftDent desktop report-pull teach / HAL policy softdent-report-pull hardening** — Prevent recurrence of export failures by hardening the HAL policy layer that governs `softdent_report_pull` (real module exists).  
3. **Optional QB stale AP/payroll refresh** — Address `importReadiness.datasetGaps` (QuickBooks AP and payroll stale 2373 min); severity is “optional” so this follows the critical path fix.  
4. **Classic Apex 2B weekly widget** — Explicitly optional; only if capacity remains after period-close hardening.

## 3. Why this beats the other candidates now
- **QB stale data** (Candidate 4) is marked `optional` severity in the audit; it does not block period close. The morning bundle failure is a hard blocker (`attest_only` fallback).  
- **Apex 2B** (Candidate 3) is explicitly labeled optional and unrelated to the `softdent_export_failed` error.  
- **Report-pull teach** (Candidate 2) is preventive maintenance; the house is currently on fire with the export failure. Hardening follows the rehearsal, not precedes it.  
- The restart proof already validated Trellis and desk smoke; the only remaining RED→GREEN transition needed is `morningBundle.ok`.

## 4. What NOT to redo
- OM schedule (built and proven in nr2-12070).  
- Trellis huddle (`/api/trellis/tomorrow-insurance` 200 OK with 27 records proven).  
- this-patient workflows.  
- PushEngage embeds (explicitly AVOID per build notes).  
- Restart proof (completed).  
- **Do not** flip `forceCloseAvailable` to `true`; it must remain `false` on GREEN+MATCH per laser-gate policy.

## 5. Acceptance criteria
- [ ] `softdent_gui_export` emits `aging.xlsx`, `register.xlsx`, `collections.xlsx` to `NewRidgeFinancial2/period_close/incoming/` (or equivalent real path).  
- [ ] PHI compliance: board initials + hash only; no full names in exported sheets.  
- [ ] `emptyNotZero` logic enforced: empty cells distinguish null from `$0` (SoftDent READ-ONLY constraint).  
- [ ] Zero SoftDent write-back operations triggered.  
- [ ] `periodCloseStatus.morningBundle.ok` transitions `true` with `failed: []` and `fallback: null`.  
- [ ] No print jobs spooled; Excel “Save As” only (no Print Preview to Printer).  
- [ ] Shadow mode confirmed: live period close state remains `completed` with fallback until explicit operator promotion.

## 6. Executive Summary (5 bullets)
- Period close is stuck in `attest_only` fallback because `softdent_export_failed` on aging, register, and collections.  
- Excel bundle rehearsal is the sole critical path item blocking hard financial close; all other lasers are GREEN.  
- Real modules `softdent_gui_export` and `hal_brain_tools_morning_bundle` exist and are ready for shadow activation.  
- QB AP/payroll staleness is optional noise (2373 min) compared to this hard blocker.  
- Laser-gates remain intact: `forceCloseAvailable` stays `false`, no restart needed, no PushEngage embeds.

## 7. Approval Checklist
- [ ] SoftDent GUI export path verified: Excel format selected (not Print Preview routed to physical printer).  
- [ ] Board PHI policy verified: initials + hash algorithm active in `hal_brain_tools_morning_bundle`.  
- [ ] Write-back safeguards confirmed: `softdent_gui_export` enforces READ-ONLY; no SQL UPDATE/INSERT paths.  
- [ ] Empty≠$0 parser logic validated: null cells preserved distinctly from zero-dollar cells.  
- [ ] Shadow run protocol acknowledged: `daily_closeout` shadow gate prevents premature promotion to live period close until export proven.
