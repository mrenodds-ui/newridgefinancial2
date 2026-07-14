# Moonshot AI — What's Next After HAL-10605 (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10605  
**Prior apply:** HAL-10605 (`99b17ef`)  
**Script:** `scripts/run_moonshot_whats_next_after_hal10605_consult.py`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> next

---

# Verdict
Deploy the operational playbook to facilitate the SoftDent **Gold CSV drop** (Insurance Payment Analysis export) so the HAL-10605 settlement_matrix can hydrate from real InsCo×ADA payment lines and pass its acceptance gate.

## 0. Operator Intent (verbatim)
next

## 1. Confirmation of HAL-10605 apply (pass/fail; residual risks)
**PASS** — Commit `99b17ef` / BUILD_ID `hal-10605` is live: settlement_matrix schema exists, TP prefer logic (viaGold > viaAlias > viaLedger) is wired, and NEW HIGH aliases (Great-west→CIGNA, Kanawha→HUMANA) are accepted.  
**Residual Risk:** `acceptanceGateMet=false` because `GOLD_CSV_MISSING`; matrixCells=0, paymentLines=0. The matrix is an empty vessel (empty != $0). Until the SoftDent Insurance Payment Analysis CSV lands, TP estimates cannot leverage the Gold spine and remain dependent on sparse ledger aliases (~46 usable cells).

## 2. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**OPS: SoftDent Gold CSV drop facilitation**  
- **Why now:** HAL-10605 code is complete but data-starved. This is the unblocker; no downstream Gold-dependent features (COB estimation, high-fidelity TP) can activate without the source CSV.  
- **Effort:** Low — operational playbook, not code. Staff training + path verification.  
- **REAL files required:** SoftDent “Insurance Payment Analysis” report exported as CSV (or XLS) to `C:\SoftDentFinancialExports\insurance_payments_YYYYMMDD.csv` (or configured sync root). File must contain historical insurance payment lines with InsCo names, ADA codes, and paid amounts.  
- **Validation gate:** ETL ingests ≥1,000 payment lines → hydrates settlement_matrix → `matrixCells` ≥200 with `n≥10` per cell → `acceptanceGateMet` flips `true`. Honesty CI remains green (inventedGold=false).

## 3. Why this beats other candidates now
- **vs CODE: HAL UI chip (2):** Surfacing viaGold/viaAlias/pending is valuable UX, but it only displays the empty state; it does not fill the matrix. Data first, visualization second.  
- **vs OPS: Coventry MEDIUM pending (3):** Only 2 aliases. Resolving them unlocks negligible TP surface area compared to hydrating the entire Gold matrix (potential 200+ cells).  
- **vs CODE: Secondary COB estimation (5):** Explicitly blocked until Gold exists; cannot estimate coordination benefits without primary InsCo×ADA settlement history.  
- **vs OPS+CODE: ERA-835 first-drop (7):** Conditional on files existing. Current gap code is `GOLD_CSV_MISSING`, not ERA file absence. If ERA files appear, this becomes a runner-up, but the Gold CSV is the known blocker today.  
- **vs CODE: Address-field mining (4) / Uncovered ledger (6):** Low-ROI workarounds that build on the fragile ledger spine. Gold CSV arrival obsoletes the need for mining guesses.

## 4. Runner-ups (2–3)
1. **CODE: HAL UI chip (2)** — Implement after Gold CSV lands to surface the newly hydrated viaGold cells vs viaAlias fallbacks, giving staff confidence in estimate provenance.  
2. **CODE: Staff catalog UX filter no_settlement vs usable (8)** — Helps staff understand which aliases are “dead” (NONE/rejected) vs active, reducing confusion while waiting for Gold hydration.  
3. **OPS+CODE: ERA-835 first-drop (7)** — **Conditional:** If physical ERA files (835) appear on disk before the Gold CSV export occurs, pivot to this immediately; ERA provides higher-fidelity payment data than the Insurance Payment Analysis CSV.

## 5. What NOT to redo
- Do **not** perform SoftDent write-back of estimates.  
- Do **not** invent Gold payment lines from DaySheet/ledger or force-match the 75 rejected aliases (TPAs/employers).  
- Do **not** rebuild HAL-10588–10605 as greenfield; build ON them.  
- Do **not** auto-accept Coventry MEDIUM without Gold evidence.  
- Do **not** treat GitHub/PR as the primary next step; the blocker is operational data procurement, not code delivery.

## 6. Acceptance criteria
- [ ] SoftDent staff can execute the export playbook: Reports → Insurance → Insurance Payment Analysis → CSV → `C:\SoftDentFinancialExports\`  
- [ ] `newestPaymentCsv` is non-null in live snapshot; `gapCode` transitions from `GOLD_CSV_MISSING` to `GOLD_CSV_PRESENT`  
- [ ] ETL ingests >0 `paymentLines`; `matrixCells` >0 (hydration started)  
- [ ] Within 48h of drop: `matrixCells` ≥200 with `n≥10` and `acceptanceGateMet=true`  
- [ ] Honesty CI remains green: `inventedGold=false`, `emptyIsNotZero=true`, no zero-filled cells

## 7. Executive Summary (5 bullets)
- HAL-10605 Gold settlement_matrix is live but empty (0 cells) pending the Insurance Payment Analysis CSV export from SoftDent.  
- The acceptance gate requires ≥200 populated InsCo×ADA cells (n≥10); current state is `GOLD_CSV_MISSING`.  
- **Next action is operational, not code:** Train staff to drop the CSV so the existing ETL can hydrate the matrix.  
- Until hydration occurs, TP estimates rely on sparse ledger aliases (~46 cells) and cannot leverage the Gold preference hierarchy.  
- No other candidate (UI, COB, address mining) unblocks the critical path; data procurement is the bottleneck.

## 8. Approval checklist
- [ ] Operator confirms SoftDent desktop access to run “Insurance Payment Analysis” report  
- [ ] Export path `C:\SoftDentFinancialExports\` exists and is writable by SoftDent user  
- [ ] Sync agent (or ETL watcher) is configured to detect `insurance_payments_*.csv`  
- [ ] Staff briefed: “Do not edit CSV before drop; empty != $0; we need raw payment lines”  
- [ ] Rollback plan: If CSV format differs from schema, ETL will reject (not crash) and log `GOLD_SCHEMA_MISMATCH` for next consult