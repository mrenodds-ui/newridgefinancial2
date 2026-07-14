# Moonshot AI — How to Derive InsCo × ADA Paid-After-Write-Off (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10576  
**Prior:** ADA payer TX consult 2026-07-10 + apply hal-10400; HAL-10581 attribution  
**Script:** `scripts/run_moonshot_insco_ada_howto_consult.py`  
**Apply:** DO NOT APPLY until operator approves.

## Operator request (verbatim)

> based on transactional history of all patients their insurance coverage, claims involved with each patient and the transactionsal history of each patients insurance write off an insurance payment can you extrapulate what each insurance plan pays for each ada code? ask moonshot ai with all the data how to do it

---

# Verdict
Extrapolate InsCo × ADA paid-after-write-off estimates by ingesting SoftDent’s **Insurance Payment Analysis** CSV (line-item payments + write-offs + ADA codes) into the hal-10400 pipeline, cross-walking internal procedure codes via **Procedure Code Listing**, and aggregating with a minimum n≥10 sample rule; the 549k ledger and 61 claims alone cannot bridge charges to payments because they lack traversable foreign keys and payment allocation details.

## 0. Operator Intent (verbatim)
> "based on transactional history of all patients their insurance coverage, claims involved with each patient and the transactionsal history of each patients insurance write off an insurance payment can you extrapulate what each insurance plan pays for each ada code? ask moonshot ai with all the data how to do it"

## 1. Can ledger+coverage+claims alone do it?
**NO.**

**Live evidence:**
- `sd_account_transactions` (549,564 rows) contains internal procedure codes (`2`, `51`, `1110`) and dollar amounts, but **zero payer attribution** and **zero claim linkage**; the `procedure` column is not an ADA code and has no foreign key to `sd_claims`.
- `sd_claims` (61 rows) now has named payers via HAL-10581 Sensei attribution, but contains **no payment amounts, write-offs, or ADA codes**; it is only claim headers.
- `sd_patient_insurance` (5,415 rows) provides patient→plan mapping but cannot link specific transactions to specific payments without the EOB-level allocation.
- **Empty ≠ $0**: The absence of `sd_insurance_payment_lines` (0 rows) means we have no paid-after-write-off data; attempting to impute this from ledger aggregate sums would fabricate false precision.

**The unblock path:** SoftDent’s **Insurance Payment Analysis** report exports line-level payment allocations (Claim #, ADA code, Submitted, Allowed, Paid, Write-Off, Patient Portion, InsCo name) which hal-10400 ingests into `sd_insurance_payment_lines`.

## 2. Correct HOW-TO
**Ordered steps — SoftDent UI + NR2 files + sync + HAL check:**

1. **SoftDent Export (Critical Path)**
   - Menu: `Reports` → `Insurance` → `Insurance Payment Analysis`
   - Parameters: Date range **Last 24 months** (or maximum available), Include all carriers, Include write-offs
   - Format: **CSV** (comma-delimited)
   - Save as: `C:\SoftDentFinancialExports\insurance_payments_YYYYMMDD.csv`

2. **Optional Crosswalk Export (Strongly Recommended)**
   - Menu: `Lists` → `Procedure Codes` → `Procedure Code Listing` (or `Reports` → `Lists` → `Procedure Codes`)
   - Include: Internal Code, ADA Code (CDT), Description
   - Save as: `C:\SoftDentFinancialExports\procedure_codes_YYYYMMDD.csv`

3. **File Drop & Validation**
   - Verify files exist in `C:\SoftDentFinancialExports\` (exact paths from LIVE SNAPSHOT)
   - Do not rename columns; hal-10400 aliases handle headers like "InsCo", "Insurance Co", "ADA", "CDT", "Write-off", "WO"

4. **Sync Ingest**
   - Run: `python import_sync.py` (or wait for scheduled sync)
   - Pipeline triggers: `run_treatment_planning_ingest()` in `softdent_treatment_planning.py`
   - Expected outcome: `sd_insurance_payment_lines` populated with line items; `treatment_planning_estimates` aggregated

5. **HAL Check**
   - Query: "How much does Delta Dental of KS pay for D0274?"
   - HAL validates `sample_size >= 10` before quoting median paid-after-write-off; otherwise returns "Insufficient data"

## 3. What each data source contributes
| Table | Role | Cannot Do |
|-------|------|-----------|
| `sd_account_transactions` (549k) | Patient visit context, internal procedure frequency, production totals | Link to specific payer; provide ADA codes; show insurance payment allocation |
| `sd_patient_insurance` (5,415) | Patient→Plan→Carrier attribution (via Sensei HAL-10581) | Provide fee schedules or historical paid amounts |
| `sd_claims` (61) | Claim headers, billed amounts, carrier names | Provide EOB-level paid amounts, write-offs, or ADA line items |
| `sd_insurance_payment_lines` (currently 0) | **The money trail**: Paid amount, contractual write-off (CO-45), patient responsibility, ADA code, InsCo name per claim line | Exist until CSV exported |
| `sd_procedure_code_reference` (currently 0) | Maps internal `111000` → `D1110`, `274` → `D0274` | Normalize without Procedure Code Listing export |
| `treatment_planning_estimates` (currently 0) | Aggregated InsCo × ADA statistics (median paid, sample size) | Provide patient-specific estimates (PHI-free aggregate only) |

## 4. Extrapolation / statistics rules
- **Sample Size Floor**: Only report estimates where `n >= 10` payment lines exist for the InsCo + ADA combination. HAL returns "Insufficient sample" if below threshold.
- **Central Tendency**: Use **median** paid-after-write-off (not mean) to resist outlier claims (complex cases, multiple teeth).
- **Secondary Insurance**: Flag when `payer_sequence > 1`; do not blend primary and secondary payments in the same estimate unless explicitly requested.
- **Deductible Honesty**: Report `patient_portion` separately; do not subtract from the "InsCo pays" figure to avoid confusion.
- **Temporal Decay**: Weight recent payments (last 12 months) higher than older (12-24 months) if sample allows; otherwise use full 24-month window.
- **Generic Payer Filter**: Exclude rows where `payer_name` = "Insurance" (unattributed) to prevent polluting named carrier estimates.

## 5. Optional enrichments
- **ERA 835 SVC Segments**: If you receive electronic remits, parsing 835 files into `svc_line` segments provides more granular "allowed amount" data than the SoftDent report; useful for validating contractual write-offs.
- **Fee Schedules**: If exported from SoftDent (`Lists` → `Fee Schedules`), can be ingested to compare "billed vs allowed" variance by InsCo, but this is **prospective pricing**, not historical paid reality.
- **Sensei Reference**: Already applied (HAL-10581); ensures `sd_patient_insurance` has current plan assignments for attribution, but does not provide historical payment amounts.

## 6. What NOT to do
- **Do NOT** attempt to join ledger `procedure` codes (`2`, `51`) to `sd_claims` via date/patient heuristic; there is no stable foreign key and this creates false matches.
- **Do NOT** treat `sd_claims` 61 rows as a proxy for the 549k transactions; claims data is incomplete and lacks payment allocation.
- **Do NOT** assume `empty` (0 rows in `sd_insurance_payment_lines`) means zero dollars; it means **data not yet exported**.
- **Do NOT** write back calculated fee schedules to SoftDent’s Ins Plan Register; HAL is read-only for treatment planning estimates.
- **Do NOT** report averages on samples < 10; this produces unreliable treatment planning guidance.

## 7. Acceptance criteria / validation gates
- [ ] `sd_insurance_payment_lines` count > 0 (target: thousands, matching ~24 months of payments)
- [ ] `treatment_planning_estimates` count > 0 (aggregated InsCo × ADA combinations)
- [ ] HAL query "What does [Carrier] pay for [ADA]?" returns numeric median (not "unknown") for top 20 procedures (D1110, D0274, etc.) with n≥10
- [ ] Crosswalk validated: Internal code `1110` maps to `D1110` in estimates
- [ ] Deductible honesty check: HAL distinguishes "Insurance pays $X" vs "Patient owes $Y"

## 8. Executive Summary (5 bullets)
- **The 549k ledger is blind to payer-specific payments**; it lacks claim-line linkage and ADA code normalization required for InsCo pricing.
- **The unblock is a single CSV export**: SoftDent Reports → Insurance Payment Analysis → 24 months → `C:\SoftDentFinancialExports\`.
- **HAL-10400 pipeline is live and waiting**; `sd_insurance_payment_lines` = 0 only because the export has not been dropped.
- **Attribution is solved** (HAL-10581 Sensei → `sd_patient_insurance`); once payments are ingested, the payer→patient→ADA join is traversable.
- **Statistics guardrails enforced**: Minimum n=10 samples, median reporting, and explicit "insufficient data" responses prevent bad treatment planning estimates.

## 9. Approval checklist (operator actions only)
- [ ] **Export**: SoftDent → Reports → Insurance → Insurance Payment Analysis (24 months) → CSV
- [ ] **Optional Export**: Procedure Code Listing → CSV (for ADA crosswalk)
- [ ] **Drop Files**: Move CSVs to `C:\SoftDentFinancialExports\` with naming pattern `insurance_payments_YYYYMMDD.csv` (and `procedure_codes_YYYYMMDD.csv`)
- [ ] **Sync**: Run `import_sync.py` (or confirm auto-sync executes)
- [ ] **Verify**: Check HAL board-action "Treatment Planning Data Status" shows `paymentLines > 0` and `estimates > 0`