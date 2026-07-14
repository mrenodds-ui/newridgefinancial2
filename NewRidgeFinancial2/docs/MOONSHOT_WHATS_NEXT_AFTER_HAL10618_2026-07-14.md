# Moonshot AI — What's next after HAL-10618 (CONSULT ONLY)

**Date:** 2026-07-14
**Model:** `kimi-k2.5`
**Key:** OPENROUTER_API_KEY
**Build:** hal-10618
**Script:** `scripts/run_moonshot_whats_next_after_hal10618_consult.py`
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> next

---

# Verdict
Deploy **OPS Gold CSV / ERA first drop for settlement truth** to hydrate the insurance payment matrix and unblock AR reconciliation.

## 0. Operator Intent (verbatim)
> next

## 1. Confirmation of HAL-10618 apply (pass/fail; residual risks)
**Pass.** All shipped artifacts confirmed in live snapshot: double-micro debris eliminated (claims/ar ops pairing cleaned), stale-import-alert logic gated to warning-only, apex-theme.css relinked, Content Hub sidebar merged (docs/narr/library consolidated), and zero-scroll Fibonacci bands populated across Financial/AR/Claims/Taxes/QuickBooks (5/5 tiles with data). **Residual risks:** Gold settlement matrix remains at 0 cells (`GOLD_CSV_MISSING`), ERA inbox empty (`ERA835_PENDING`), and critical QuickBooks datasets (P&L, Revenue) are 35+ hours stale—system is UI-ready but data-blind on insurance payments and stale on financials.

## 2. Recommended NEXT (name, why now, effort, REAL files or OPS steps, validation gate)
**B) OPS Gold CSV / ERA first drop for settlement truth**

**Why now:** The UI surface achieved zero-scroll acceptance in HAL-10618; further layout surgery yields diminishing returns. The critical path is practice truth—specifically the **Insurance Payment Analysis** export from SoftDent (Gold) and the first **ERA 835** drop. Without these, the settlement matrix cannot hydrate (`cellsNge10=0`), OCR expansion remains stopped, and staff sees permanent "UNVERIFIED SCANNED ESTIMATE" banners. This is the highest ROI unblocker: it moves the system from "staff-ready UI" to "operationally trustworthy data."

**Effort:** OPS-only (no code deploy). Requires desk-side at SoftDent workstation and file share configuration (≈30–45 min).

**REAL files or OPS steps:**
1. **SoftDent Desktop → Office Manager → Reports → Insurance Payment Analysis** → Export to `C:\SoftDentFinancialExports\` as CSV or XLSX (filename pattern: `InsurancePaymentAnalysis_YYYYMMDD.csv`).
2. **Verify HAL service account** has read/write to `C:\SoftDentFinancialExports\` (snapshot confirms path exists and writable; reconfirm after export).
3. **Create ERA inbox:** Establish `C:\SoftDentFinancialExports\ERA_Inbox\` (or path configured in HAL env).
4. **Configure clearinghouse:** Route 835 ERA files to the inbox (or coordinate manual drop of first remittance file).
5. **Trigger HAL sync:** Force import reload or await next poll; verify ETL ingests Gold CSV (expect `paymentLines > 0`).
6. **Confirm hydration:** Settlement matrix should populate (`matrixCells > 0`, `cellsNge10` approaching 200).

**Validation gate:** `goldEra.gold.acceptanceGateMet === true` (i.e., `cellsNge10 >= 200`) **AND** `goldEra.era.fileCount > 0` (or `goldEra.readiness.goldReady === true` and `eraReady === true`).

## 3. Why this beats other candidates now
- **A) OPS SoftDent period refresh:** Addresses stale claims/production (30+ hours) but uses DaySheet/Register exports which the snapshot explicitly states are *not* ADA×InsCo gold lines; this will not unblock the settlement matrix or remove the "UNVERIFIED" banner.
- **C) CODE SoftDent Report Manager rights:** Rights automation is premature—the immediate blocker is that the Gold CSV has never been exported, not that the code cannot pull it. Automate after the first manual drop proves the pipe.
- **D/E) Content Hub polish / zero-scroll smoke:** UI is already staff-ready (census shows 5/5 tiles populated on all financial pages); further layout work is lower ROI than fixing data blindness.
- **F) CODE HAL/import honesty:** Shipped in HAL-10618 (`forceShow` on Financial/SoftDent, stale chips with `ageMinutes`); remaining work is cosmetic versus the critical Gold/ERA gap.

## 4. Runner-ups (2–3)
1. **A) OPS SoftDent period refresh** — Fix the 35-hour stale QB P&L/Revenue and SoftDent claims/production staleness. Important for daily ops, but less critical than the completely missing Gold settlement data.
2. **C) CODE SoftDent Report Manager rights / multi-pull reliability** — If OPS steps reveal permission errors during Gold export automation (e.g., Report Manager credentials expiring), escalate to this code package to harden the pull mechanism.
3. **F) CODE HAL/import honesty refinement** — If stale chips continue to mislead staff after data is refreshed, refine the `ageMinutes` thresholds; otherwise, defer.

## 5. What NOT to redo
- **Do not rearrange tiles or bands.** Zero-scroll Fibonacci layout is achieved and staff-ready; avoid further layout churn.
- **Do not add new widget types** to fill space (census confirms all pages are 5/5 or 4/4 populated).
- **Do not expand OCR.** Policy explicitly stopped OCR expansion (`ocrExpansionStopped: true`) pending settlement truth; do not reverse this until Gold/ERA validates.
- **Do not invent Gold dollars.** Maintain `emptyIsNotZero` honesty—do not populate settlement matrix with DaySheet approximations or estimates.

## 6. Acceptance criteria
- [ ] `C:\SoftDentFinancialExports\` contains `Insurance Payment Analysis` CSV/XLS with `paymentLines > 0`
- [ ] HAL ingest logs show `matrixCells > 0` and `cellsNge10` ≥ 200 (acceptance gate)
- [ ] `goldEra.gold.gapCode` transitions from `GOLD_CSV_MISSING` to `null` or `GOLD_OK`
- [ ] `goldEra.gold.acceptanceGateMet === true`
- [ ] ERA inbox receives first 835 file (`fileCount > 0`) or `goldEra.era.chipStatus` moves from "awaiting"
- [ ] "UNVERIFIED SCANNED ESTIMATE" banner disappears or updates to settlement-ready state
- [ ] OCR policy reflects that settlement truth is now available for verification

## 7. Executive Summary (5 bullets)
- HAL-10618 delivered a staff-ready, zero-scroll UI across all financial surfaces; the remaining blocker is data truth, not layout.
- Gold CSV (SoftDent Insurance Payment Analysis) is entirely missing, preventing settlement matrix hydration (0 cells) and stopping OCR verification.
- ERA 835 inbox is empty, blocking structured remittance operations and forcing reliance on unverified scanned estimates.
- This OPS package requires only file export and drop configuration—no code deploy—and directly unblocks the highest-value reconciliation workflows.
- Completing this enables the Gold/ERA settlement matrix, validates AR aging, and removes the permanent "UNVERIFIED" warnings, making the financial surface operationally trustworthy.

## 8. Approval checklist
- [ ] Office Manager confirms access to SoftDent **Insurance Payment Analysis** report (not just DaySheet/Register)
- [ ] IT confirms `C:\SoftDentFinancialExports\` writable by HAL service account and accessible from HAL hub
- [ ] Clearinghouse contact confirmed for ERA 835 routing (or manual drop process documented)
- [ ] Staff briefed that `empty ≠ $0` until Gold/ERA validation completes (no invented dollars)
- [ ] Fallback acknowledged: Desktop SoftDent Excel/Print Preview remains period-close truth if HAL automation fails
