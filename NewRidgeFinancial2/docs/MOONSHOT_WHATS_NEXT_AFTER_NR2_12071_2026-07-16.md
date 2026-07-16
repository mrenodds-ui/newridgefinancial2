# Moonshot AI — What's Next After nr2-12071 (CONSULT ONLY)

**Date:** 2026-07-16
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Script:** `scripts/run_moonshot_whats_next_after_nr2_12071_consult.py`
**Closed:** `168c385` nr2-12071 Trellis benefits counts + SoftDent Preview teach
**Apply:** Operator said continue — Cursor may apply Recommended NEXT.

## Operator request (verbatim)

> continue

---

# Verdict
Harden SoftDent collections (Practice Management F10) to Print Preview export to unblock morningBundle money beams; File dialog is unreachable and must not be invented.

## 0. Operator Intent (verbatim)
continue

## 1. Recommended NEXT (name, why now, effort, REAL files under NewRidgeFinancial2/, validation gate)
**SoftDent collections Print Preview harden (Practice Management F10)**
- **Why now:** LIVE AUDIT shows morningBundle.ok=false with `softdent_export_failed` on aging/register/collections. Error trace indicates SoftDent “Select File Name” dialog has no path and the system correctly refuses to invent a directory. SoftDent Output Options constraint mandates Excel OR Print Preview only — NEVER File. Print Preview is the only viable path to extract money beams without write-back or directory invention.
- **Effort:** Small polish (refactor export trigger in existing HAL teach path).
- **REAL files:**  
  - `NewRidgeFinancial2/softdent_gui_export.py` (optical JS/Python bridge)  
  - `NewRidgeFinancial2/softdent_report_pull.py` (report orchestration)  
  - `NewRidgeFinancial2/hal_softdent_teach.json` (Preview-lock config)
- **Validation gate:**  
  - morningBundle.ok transitions `false → true` for aging, register, collections  
  - morningBundle.failed array empties of these three items  
  - `empty ≠ $0` preserved (no zero-injection on empty result sets)  
  - `forceCloseAvailable` remains `false` (laser-gated; no flip on MATCH/GREEN alone)

## 2. Ordered backlog AFTER #1 (2–4)
2. **Wire withBenefits into desk-smoke / morningConfidence** — eligibilityReport currently shows `withBenefits: 0` despite schema `nr2-12071` expecting counts; integrate the new surface into confidence scoring once export is stable.  
3. **Restart NR2 + prove eligibility-report withBenefits live** — validate that the 12071 build actually populates benefit counts after #1 stabilizes the data pipe; confirm no rollback to old build.  
4. **Classic Apex 2B (optional only)** — final period-close hardening only after morningBundle money beams are proven stable and withBenefits gap is closed.

## 3. Why this beats the other candidates now
- **#2 (Excel enablement / HAL teach):** Already completed in nr2-12071 closed docs; Excel remains greyed in SoftDent and we are forbidden from inventing Excel file drops to fake `morningBundle.ok=true`.
- **#3 (Classic Apex 2B):** Optional and premature while money beams are blocked; Apex 2B assumes stable report ingestion.
- **#4 (Wire withBenefits):** Secondary to the export failure; without working Print Preview, there is no data surface to wire into confidence metrics.
- **#5 (Restart NR2):** Build stamp already shows `nr2-12071-trellis-benefits-surface`; restart will not resolve the fundamental File-vs-Preview mismatch causing the export RuntimeError.

## 4. What NOT to redo
- Do **not** attempt to fix SoftDent File path by inventing directories, registry hacks, or enabling “Save As” automation.
- Do **not** flip `forceCloseAvailable` to `true` solely on `deskProof: MATCH` / `status: GREEN`.
- Do **not** demand `morningBundle.ok=true` via phantom Excel file drops or simulated exports.
- Do **not** rebuild: OM schedule, Trellis huddle PHI scrub, this-patient view, PushEngage hooks, benefits HTML surface, or the already-delivered HAL teach.

## 5. Acceptance criteria
- [ ] SoftDent F10 Practice Management → Collections (and aging/register) export via **Print Preview** without triggering “Select File Name” dialog.
- [ ] `morningBundle.ok` becomes `true` for aging, register, collections; `failed` list excludes these three.
- [ ] Empty result sets handled as `null`/`[]`, never coerced to `$0`.
- [ ] `forceCloseAvailable` remains `false` until independent laser-gate conditions are met.
- [ ] No new File-path dependencies introduced in `softdent_gui_export.py`.

## 6. Executive Summary (5 bullets)
- **Blocker:** morningBundle money beams (aging/register/collections) are down due to SoftDent File dialog failure; we refuse to invent directories.
- **Solution:** Harden F10 Practice Management path to use **Print Preview** exclusively, satisfying “Excel OR Print Preview only — NEVER File” constraint.
- **Impact:** Unblocks period-close data ingestion without write-back or PHI exposure.
- **Risk:** withBenefits count remains at 0 until backlog item #2; acceptable because money beam stability precedes benefits analytics.
- **QB Status:** AP/payroll remain stale (optional, staff-dependent); no SDK automation attempted.

## 7. Approval Checklist
- [ ] Operator confirms SoftDent “File” dialog is inaccessible (greyed or pathless) and **Print Preview** is visible and functional.
- [ ] Risk accepted: `withBenefits: 0` persists until post-export wiring (#2).
- [ ] Acknowledged: `forceCloseAvailable` will **not** flip to `true` upon completion of this package alone.
- [ ] REAL file paths confirmed: `softdent_gui_export.py`, `softdent_report_pull.py` exist under `NewRidgeFinancial2/`.
- [ ] No React/phantom modules introduced; pure Python + optical JS automation only.
