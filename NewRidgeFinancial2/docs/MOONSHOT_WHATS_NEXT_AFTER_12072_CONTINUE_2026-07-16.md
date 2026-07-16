# Moonshot AI — What's Next After nr2-12072 Continue (CONSULT ONLY)

**Date:** 2026-07-16
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_whats_next_after_12072_continue_consult.py`
**Closed:** ee53f4c continue proof + bd435ae Preview harden
**Apply:** Operator must say continue / approve before Cursor applies.

## Operator request (verbatim)

> next

---

# Verdict
Recommend **SoftDent Excel enablement operator runbook + attended morning-bundle re-run gate** to resolve the active `softdent_export_failed` blocker that prevents `morningBundle.ok` from flipping true.

## 0. Operator Intent (verbatim)
next

## 1. Recommended NEXT (name, why now, effort, REAL files under NewRidgeFinancial2/, validation gate)
**SoftDent Excel enablement operator runbook + attended morning-bundle re-run gate (no invent Excel)**

- **Why now**: LIVE AUDIT shows `periodCloseStatus.morningBundle.ok=false` with error `softdent_export_failed` and detail: *"SoftDent Select File Name has no path — refuse inventing a directory."* This is the mechanical blocker preventing period close. Desk smoke is GREEN/MATCH, but `forceCloseAvailable` is laser-gated false until the bundle succeeds. The automation cannot invent directories; SoftDent must be attended to expose its own folder (e.g., `OneDrive\Documents\AcctAge`).

- **Effort**: Low (operator documentation + single attended session).

- **REAL files under NewRidgeFinancial2/**:
  - `softdent_gui_export.py` (existing automation surfacing the path error)
  - `desk_smoke.py` (validates `morningBundle.ok` and `forceCloseAvailable` gating)
  - `docs/runbooks/softdent_excel_enablement_nr2.md` (to be created: operator steps to open SoftDent → Output Options → Excel, set valid export directory, and save)

- **Validation gate**:
  1. Operator follows runbook to set SoftDent export directory for aging/register/collections.
  2. Re-run morningBundle automation.
  3. Confirm `softdent_export_failed` clears and `morningBundle.ok` transitions to `true` (or `partial=true` with valid exports, not `attest_only`).
  4. Verify exported Excel files appear in the designated directory with non-empty content (respecting `empty≠$0` constraint).

## 2. Ordered backlog AFTER #1 (2–4)
1. **Wait / monitor tonight Trellis benefits scrape; surface withBenefits>0 proof tomorrow AM** (Candidate 2) — Validate that the 10:10 PM ClearCoverage scrape populates benefits for the 25 status-only patients, enabling `morningConfidence.trellisBenefits` with real dollars.
2. **Optional QB AP/payroll inbox drop checklist (staff exports)** (Candidate 3) — Address the stale optional datasets (2444 min old) via manual staff export process to shared inbox, since SDK remains unavailable.
3. **Classic Apex 2B (optional only)** (Candidate 4) — Post-close reconciliation package, executed only if accounting requires it after the main close completes.

## 3. Why this beats the other candidates now
- **Candidate 2 (Trellis scrape)** is scheduled for tonight but cannot resolve the SoftDent export path issue; benefits data is secondary to the mechanical blocker of ingesting aging/register/collections into the money beam.
- **Candidate 3 (QB datasets)** is explicitly marked `optional`/`stale` in LIVE AUDIT and does not block `forceCloseAvailable`.
- **Candidate 4 (Apex 2B)** is optional and premature while `morningBundle.ok=false` persists.
- The laser-gated `forceCloseAvailable=false` requires `morningBundle.ok=true`; no other candidate addresses this dependency.

## 4. What NOT to redo
OM schedule, Trellis huddle PHI handling, benefits HTML surface, Preview Date Wizard harden (already shipped in nr2-12072), this-patient logic, PushEngage integration, or creating phantom modules like `hal_softdent_teach.json`.

## 5. Acceptance criteria
- [ ] Runbook exists at `NewRidgeFinancial2/docs/runbooks/softdent_excel_enablement_nr2.md` with operator-specific paths (e.g., OneDrive/Documents).
- [ ] Operator attest logged: "SoftDent export directory manually set to [real path]" before re-run.
- [ ] Re-run morningBundle: aging, register, collections exports succeed (no "Select File Name has no path" error).
- [ ] `morningBundle.ok` transitions from `false` to `true` (or `partial=true` with valid exports, not `attest_only`).
- [ ] Exported files respect READ-ONLY constraint and `empty≠$0` semantics (no write-back).
- [ ] `forceCloseAvailable` remains `false` until validation confirms (no premature flip on GREEN/MATCH alone).

## 6. Executive Summary (5 bullets)
- **Active Blocker**: SoftDent Excel export path unset causes `morningBundle.ok=false`, preventing period close despite GREEN desk smoke.
- **Mechanical Fix Required**: Cannot invent directories programmatically; requires attended operator runbook to configure SoftDent Output Options.
- **Laser-Gated Close**: `forceCloseAvailable` remains false until morningBundle succeeds; Preview Date Wizard harden alone insufficient for `moneyBeamIngest`.
- **Secondary Pipeline**: Trellis benefits scrape scheduled for tonight will populate status-only rows but depends on export fix for ingestion.
- **Optional Data**: QB AP/payroll datasets stale but explicitly optional; not blocking close flow.

## 7. Approval Checklist
- [ ] No phantom file paths invented (e.g., `hal_softdent_teach.json`).
- [ ] No `forceCloseAvailable` flip logic added without `morningBundle.ok` validation.
- [ ] No SoftDent directory creation in code (respect "refuse invent dirs").
- [ ] No redo of shipped items (Preview Date Wizard, etc.).
- [ ] REAL module paths referenced (`softdent_gui_export.py`, `desk_smoke.py`).
