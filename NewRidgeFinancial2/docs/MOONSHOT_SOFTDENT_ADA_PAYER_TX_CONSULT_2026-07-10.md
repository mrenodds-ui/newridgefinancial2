# Moonshot AI — SoftDent Charge → Insurance Paid → ADA for HAL Treatment Planning

**Date:** 2026-07-10  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Endpoint:** https://api.moonshot.ai/v1/chat/completions  
**Status:** ok  
**Build reviewed:** hal-10390  
**Script:** `scripts/run_moonshot_softdent_ada_payer_tx_consult.py`  
**Apply:** Report only — do not code until operator approves.

## Operator request (verbatim)

> ask moonshot ai about softdent.  ask him if he can pull transactions off patients' list from charges to what insurance paid for those transactions and then tie it back to the insuance company to figure how much they paid for ada dental claim code after write off so we can teach hal how to do treatment planning.

---

# Verdict: PARTIAL

## 0. Operator Intent (quote verbatim)
> "ask moonshot ai about softdent. ask him if he can pull transactions off patients' list from charges to what insurance paid for those transactions and then tie it back to the insuance company to figure how much they paid for ada dental claim code after write off so we can teach hal how to do treatment planning."

## 1. SoftDent Data Model for Charge → Paid → Payer → ADA
Conceptually, SoftDent maintains:
- **Charges**: Service transactions with ADA/CDT codes (e.g., D0120, D1110) linked to patients/providers
- **Claims**: InsCo-specific claim headers (primary/secondary payers, claim numbers)
- **Claim Line Items**: Individual procedures per claim with submitted fees
- **Insurance Payments**: EOB-level payments with allowable amounts, paid amounts, and CO-45 (contractual write-off) adjustments
- **Patient Responsibility**: Remaining balance after InsCo payment + write-off
- **Adjustment Reasons**: Write-offs ( contractual, courtesy, bad debt) linked to specific transactions

However, **LIVE FACTS show this conceptual model is NOT traversable in NR2's current data lanes**.

## 2. What NR2 Has Today (live evidence)
**Current viable lanes (hal-10390):**
- `sd_transactions_full` (1,284 rows): Contains charges, payments, adjustments with dates/amounts
- `sd_procedures` (25,757 rows): Contains production by internal SoftDent codes (12000, 111000 format), NOT canonical D-codes; **zero payment/write-off data**
- `sd_claims` (61 rows): Contains payer names, but **60/61 are generic "Insurance"** (useless for InsCo-specific learning), only 1 "Delta Dental"
- Insurance analytics tables: **All empty (0 rows)** — schema exists but no data flowing

**Critical data quality failures:**
- `payer` field: **0% populated** in transactions and payments
- `claim_id` field: **0% populated** in transactions (no charge-to-claim linkage)
- `transaction_code`: **Dollar amounts masquerading as codes** ("56.00", "305.00") instead of CDT codes
- `ada_code` column: Polluted with values like 137, 100, 11.93 (not D0120 format)
- **No write-off/CO-45 amounts** captured in any current export

## 3. Gap Analysis (why the join fails today)
**The NR2 operator cannot perform the requested calculation today because:**

1. **Missing Claim Linkage**: `sd_transactions_full` has no `claim_id` or `original_transaction_id` populated, making it impossible to group charges with their insurance payments and write-offs
2. **Missing Payer Attribution**: 0% payer population means no ability to learn "Delta Dental pays X% for D0274" vs "Cigna pays Y%"
3. **Corrupted Procedure Codes**: Current export maps dollar strings to `ada_code`, rendering code-based fee schedule analysis impossible
4. **No Write-off Capture**: Contractual write-offs (CO-45) are not exported in the `transactions_for_period.jsonl` lane; only pure "adjustment" types appear without insurance linkage
5. **Insufficient Claims Volume**: Even if populated, 61 claims (mostly generic "Insurance") is statistically insufficient for machine learning

**Result**: HAL cannot compute "InsCo X paid $Y after $Z write-off for D-code" today.

## 4. Feasible Paths Ranked (MUST / SHOULD / NICE)

### MUST (Required for viable training data)
**SoftDent "Insurance Payment Analysis" Report** (or equivalent) → `insurance_payment_distribution` table
- Export: Insurance Payment Distribution report (SoftDent Reports → Insurance → Insurance Payment Analysis)
- Contains: Check #, InsCo name, Claim #, Procedure code (canonical), submitted fee, allowed amount, paid amount, write-off amount, patient portion
- Drop zone: `C:\SoftDentFinancialExports\insurance_payments_*.csv` → map to `insurance_payment_distribution` schema
- **This closes the gap**: charge fee → write-off → insurance paid → InsCo name → ADA code

**SoftDent "Insurance Claims" Detail Report** → `insurance_claims` table  
- Export: Claims with line-item detail (not summary)
- Contains: Claim ID, Patient ID, Service dates, Procedure codes, Status, Primary/Secondary InsCo
- Enables: Linkage between charges and specific payers

### SHOULD (Significantly improves HAL accuracy)
**Procedure Code Mapping Fix**
- SoftDent uses internal codes (12000 = D0120, 111000 = D1110) in Sensei `sd_procedures`
- Export SoftDent Procedure Code table with `internal_code` → `ada_cdt_code` mapping
- Load to new `procedure_code_reference` table
- Without this, HAL learns on useless internal codes

**EOB/Explanation of Benefits Export**
- Export from SoftDent Claims Module: EOB detail with denial codes
- Load to `insurance_check_distribution` (schema ready, 0 rows)
- Provides: Adjustment reason codes (CO-45, PR-2, etc.) for write-off categorization

### NICE (Advanced accuracy)
**ERA 835 Parsing** (if SoftDent generates or stores 835s)
- Electronic Remittance Advice contains the most granular adjudication: line-item allowed amount, paid amount, CAS segments for adjustments
- Parse to `insurance_income` + `insurance_adjustments` tables
- **Overkill if manual reports work**, but eliminates manual CSV exports

## 5. How HAL Should Learn Treatment Planning (once data exists)
**Architecture Rule**: HAL must NEVER store PHI in `learned_memories.jsonl` (per existing governance).

**Implementation**:
1. **Analytics Aggregates Only**: Build nightly aggregation table `treatment_planning_estimates`:
   - `insurance_company` (hashed or generic "Delta Dental PPO")
   - `ada_code` (canonical D-code)
   - `submitted_fee_avg`, `allowed_amount_avg`, `paid_amount_avg`, `write_off_avg`
   - `patient_portion_avg` (calculated as allowed - paid)
   - `sample_size` (row count)
   - **No patient_ids, no dates of service, no specific dollar amounts from individual cases**

2. **HAL Runtime Behavior**:
   - When staff asks "How much will Delta pay for D0274?", HAL queries the aggregate table
   - Response format: *"Based on [N] historical claims, Delta Dental PPO typically allows [X] for D0274 (bitewings), paying [Y] after contractual write-off of [Z]. Patient portion averages [W]. This is an estimate, not a guarantee of benefits."*
   - If sample_size < 10, HAL responds: *"Insufficient historical data for reliable estimate; contact payer for pre-auth."*

3. **Memory Storage**: 
   - Staff teaching ("Remember that Delta denies D4342 often") → `learned_memories.jsonl` (business logic only)
   - Financial patterns → Analytics tables only (no PHI)

## 6. Risks / PHI / Honesty
**PHI Boundaries**:
- **NEVER** put individual patient transactions, specific dollar amounts from real patients, or dates of service into `learned_memories.jsonl`
- Aggregate statistics (averages, percentiles) with n≥10 are safe for HAL recall
- InsCo names in aggregates are acceptable (business intelligence, not PHI)

**Honesty Rules**:
- **Estimates vs Guarantees**: HAL must always qualify responses with *"This is an estimate based on historical data; actual benefits depend on remaining deductible, annual max, and specific plan limitations."*
- **No Invented Allowed Amounts**: If `allowed_amount` is NULL in data, HAL cannot compute patient portion. Must say: *"Allowed amount unknown in historical data; verify with payer."*
- **Confidence Intervals**: HAL should express uncertainty when variance is high (std dev > 20% of mean)

**Regulatory**:
- Treatment planning estimates must not violate "no surprises" billing rules; HAL suggestions are for planning only, not patient-facing quotes without verification

## 7. Operator Next Actions
**Immediate (This Week)**:
1. **Export from SoftDent**:
   - Navigate: Reports → Insurance → **Insurance Payment Analysis** (or Insurance Income Report)
   - Date range: Last 24 months (for statistical relevance)
   - Format: CSV
   - **Critical columns to include**: Insurance Company Name, Procedure Code, Procedure Description, Submitted Fee, Allowed Amount, Paid Amount, Write-Off Amount, Patient Portion, Claim Number, Patient ID (for internal linkage only)

2. **Export Procedure Code Crosswalk**:
   - Reports → Procedures → **Procedure Code Listing**
   - Include: Internal Code, ADA Code (D-code), Description, UCR Fee
   - Purpose: Map Sensei's "12000" codes to "D0120"

3. **File Drop**:
   - Place exports in: `C:\SoftDentFinancialExports\`
   - Naming convention: `insurance_payments_YYYYMMDD.csv`, `procedure_codes_YYYYMMDD.csv`
   - Notify NR2 maintainer to map to existing empty schema tables

**Validation Steps**:
4. **Verify Data Quality**: Check that exported Procedure Codes are canonical (D0120, not 12000). If still internal codes, require the crosswalk export before HAL training begins.
5. **Check Payer Granularity**: Ensure Insurance Payment Analysis shows specific "Delta Dental PPO" not generic "Insurance" — if generic, HAL cannot learn company-specific patterns.
6. **Confirm Write-offs**: Verify CSV contains separate columns for "Write-Off" or "Adjustment" — this is the CO-45 amount needed for post-write-off calculations.

**What HAL Can Say Today (Pre-Data)**:
*"I don't have access to detailed insurance payment history yet. I can see charges and total payments, but I cannot determine which insurance company paid what amount for specific procedure codes after write-offs. Please export the Insurance Payment Analysis report so I can learn realistic allowed amounts and patient portions for treatment planning estimates."*

**Once data is loaded**: HAL can begin generating estimates with appropriate confidence intervals and honesty qualifiers described in Section 6.