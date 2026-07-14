# Moonshot AI — Dental Insurance Industry Knowledge (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10604  
**Script:** `scripts/run_moonshot_dental_insurance_industry_consult.py`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> ask moonshot ai about his full knowledge of dental insurance industry wide and anything that can help us with this program consult.

---

# Verdict  
The single biggest lever for accurate Treatment Planning is ingesting the **Gold CSV (sd_insurance_payment_lines)** to hydrate the InsCo×ADA settlement matrix, because the current ledger-based spine is too sparse (46 cells) and the remaining 77 rejected aliases are honest NONEs (TPAs/employers) that cannot yield reliable estimates without ground-truth payment data.

## 0. Operator Intent (verbatim)  
ask moonshot ai about his full knowledge of dental insurance industry wide and anything that can help us with this program consult.

## 1. Industry map for SoftDent RCM (carriers / Blues / Delta / MA / Medicaid / federal / TPA-ASO / employer-union / discount — what each means for TP $)

| Segment | Identity & Settlement Behavior | SoftDent TP Impact |
|---------|-------------------------------|-------------------|
| **National Carriers** (Aetna, Cigna, MetLife, UnitedHealthcare) | Own risk; publish UCR/schedule fees; national networks but state fee variants. | **High-confidence estimates** possible once Gold/ERA maps the specific state fee schedule. |
| **Blue Cross Blue Shield** (36 independent plans) | State-specific risk bearing; FEP Blue is the federal exception (administered by BCBSA but claims pay through local Blues). | **Must resolve to state chapter** (e.g., BCBS OF KS). "BCBS" alone is unestimable without geography. |
| **Delta Dental** (39 independent chapters) | State-specific risk; shared PPO/Premier networks but fee schedules vary by chapter. | **Must resolve to state chapter** (e.g., DELTA DENTAL OF KS). Generic "Delta Dental" defaults to local chapter only if office geography is known. |
| **Medicare Advantage Dental** | Embedded (D-SNP) or standalone. Carriers: Aetna MA, UHC MA, Humana MA, etc. Often administered via separate dental vendor (e.g., DentaQuest, Liberty). | **Coordination risk**: MA dental often pays secondary to primary medical; without COB flags in SoftDent, estimates default to primary only. |
| **Medicaid / DentaQuest** | State-administered; fee-for-service or MCO capitation. DentaQuest acts as carrier in many states (KS, TX, etc.). | **Low variance, high write-off**: Fee schedules are fixed (often 30-50% UCR), but SoftDent ledger shows capitation adjustments that look like $0 payments—Gold CSV required to distinguish true payment from cap write-off. |
| **Federal Programs** | **FEP Blue Dental** (BCBS federal); **GEHA** (now part of UnitedHealth); **UCCI** (United Concordia TDP/FED VIP). | **Stable fee schedules** published by OPM; estimates can be rule-based if payer identity is exact. |
| **TPAs / ASOs** (Allied Benefit, UMR, EBMS, CoreSource) | Administrative Services Only—no risk. Employer is the payer. Claims address shows TPA, but EOB/EFT comes from employer’s risk bearer (often a major carrier). | **Unestimable without Gold**: The TPA name tells you nothing about the underlying fee schedule. Must remain **NONE** until payment data reveals the actual risk bearer. |
| **Union / Employer Self-Funded** (Operating Engineers, Tyson Foods, etc.) | Self-insured; TPA administers. Plan design is custom (not standard commercial). | **Unestimable**: Fee schedules are plan-specific; only historical Gold payments from that specific employer group can train the estimate. |
| **Discount Networks** (DenteMax, Careington, Protective Dentalcare) | Not insurance—no settlement. Patient pays discounted fee at time of service. | **$0 insurance estimate**; SoftDent offices often mistakenly create an InsCo entry for these. Must map to **NONE** (patient responsibility only). |

## 2. SoftDent office realities (company master pollution, claim address names, plan-year junk rows, ASO shells, how other offices keep masters clean)

**Pollution Patterns (Midwest/KS-adjacent GP offices):**
- **Plan-Year Junk**: Staff create new Insurance Company entries for each benefit year (“2025 - cOMPLETE”, “Aetna 2024”). These are not distinct payers; they fragment the ledger and create orphan aliases.
- **ASO Shells**: When staff don’t know the actual carrier, they select or create “Administrative Services Only” or the TPA name (e.g., “EBMS”). The **Claim Address** field often contains the real payer (e.g., “Cigna Dental” buried in the address lines), while the Company Name field is useless.
- **Employer Naming**: Large local employers (Tyson Foods, Wichita Police Dept., Operating Engineers Local 101) appear as discrete InsCo masters even though the risk bearer is a national carrier (often UHC or Cigna).
- **Misspellings & Abbreviations**: “Insurnace”, “cOMPLETE”, “Ahc”, “Bma”, “Cna” proliferate because SoftDent does not enforce reference integrity on the Insurance Company table.

**Hygiene Playbooks (observed in clean offices):**
- **Claim Address Mining**: Regex parse the Address1/Address2/City fields for carrier keywords (“Cigna”, “Aetna”, “Delta”) to map ASO shells to spine carriers.
- **Annual Master Purge**: Offices run a pre-year-end audit: delete or inactivate plan-year suffixes; merge duplicates into the canonical spine carrier.
- **Locking the Master**: Restrict “Add New Insurance Company” permissions to billing managers; force selection from a pre-scrubbed reference list (your `insurance_company_reference` table).

## 3. Rebrand / acquisition cheat sheet (still actionable vs this spine)

| Legacy Master (in rejected/pending) | Spine Target | Band | Rationale |
|-------------------------------------|--------------|------|-----------|
| **Assurant** | SUN LIFE FINANCIAL | **HIGH** (shipped 10604) | Group benefits acquired by Sun Life 2016. |
| **Connecticut General** | CIGNA DENTAL | **HIGH** (shipped 10604) | Merged into CIGNA 1982. |
| **Met Life** (all variants) | METLIFE DENTAL | **HIGH** (shipped 10604) | Same entity, employer suffixes irrelevant to settlement. |
| **UniCare** | ANTHEM - 1115 | **HIGH** (shipped 10604) | Wholly owned Anthem subsidiary. |
| **Coventry** / **Coventry Health Care Of Kansas** | AETNA | **MEDIUM** (pending) | Acquired by Aetna 2013; legacy blocks may still adjudicate under Coventry BIN/PCN but settle via Aetna financials. Await Gold confirmation. |
| **Great-west** / **Great-West Healthcare** | **CIGNA DENTAL** | **NEW HIGH** | Acquired by Cigna 2008; remaining SoftDent masters are legacy blocks now fully on Cigna fee schedules. |
| **Kanawha** / **Kanawha Benefit Solutions, Inc** | **HUMANA DENTAL** | **NEW HIGH** | Acquired by Humana 2007; dental claims now settle under Humana financials. |
| **Definity** | UNITED HEALTHCARE | MEDIUM | Acquired by UHC 2004; older blocks may have migrated, but variance exists without Gold proof. |
| **Travelers** | METLIFE DENTAL | MEDIUM | Group benefits sold to MetLife 1996; very stale data, risk of mis-estimation if plan is grandfathered. |
| **Safehealth** | SUN LIFE FINANCIAL | MEDIUM | Acquired by Fortis→Assurant→Sun Life (chain); without payment line proof, do not auto-accept. |
| **Rural Carrier Benefit Plan** | FEP BLUE DENTAL or BCBS State | LOW/NONE | Administered by various Blues depending on USPS district; cannot assume spine target without Gold evidence. |

## 4. Leftover 77 rejected — industry triage categories + any NEW HIGH you dare (only if spine target exists; else NONE)

**Triage Categories:**

| Category | Count | Examples | Disposition |
|----------|-------|----------|-------------|
| **Plan-Year Markers / Junk** | 5 | `2025 - cOMPLETE`, `3` | **NONE** (delete from master). |
| **ASO/TPA Shells** | 25 | `Administrative Services Only`, `Allied Benefit Systems, LLC`, `EBMS`, `UMR`, `Core Source Tucson`, `Group Administrators, Ltd` | **NONE** (unestimable without underlying risk bearer). |
| **Employer / Union Specific** | 20 | `Tyson Foods`, `Wichita Police Dept.`, `Operating Engineers Local 101`, `Bricklayers Allied Company`, `Beauty First` | **NONE** (self-funded; fee schedule is employer-specific). |
| **Ambiguous Abbreviations** | 10 | `Ahc`, `Bma`, `Bsi`, `Cna`, `Gsa` | **NONE** (cannot map without address mining or staff interview). |
| **Discontinued / Niche (no spine successor)** | 15 | `Bankers Life`, `American National Insurnace`, `Centennial Life`, `Nippon Life`, `Cuna Mutual Group` | **NONE** (carrier defunct or not in network; if claims exist, they are run-out). |
| **Federal / Postal (unclear admin)** | 2 | `Rural Carrier Benefit Plan`, `Postmasters Benefit Plan` | **NONE** (could be FEP or specific BCBS; Gold required to identify actual payer). |

**NEW HIGH Proposals (spine target exists, acquisition is certain):**
- `Great-west` → **CIGNA DENTAL** (acquired 2008, fully absorbed).
- `Kanawha Benefit Solutions, Inc` → **HUMANA DENTAL** (acquired 2007).

*All other 75 remain honest NONEs.*

## 5. Gold / ERA / Register — industry truth of what files unlock what estimates

| Data Source | Content | Unlocks | Current Status |
|-------------|---------|---------|----------------|
| **Gold CSV** (`sd_insurance_payment_lines`) | Posted insurance payments (check/EFT amount, date, InsCo, claim #) | **Exact InsCo×ADA averages** (paid amount, not charged); distinguishes true payment from adjustment/write-off. | **MISSING** (0 rows). |
| **ERA 835** | Electronic Remittance Advice (allowed amount, patient responsibility, adjustment codes, PR codes) | **Allowed fee schedule derivation**; reason codes explain why payment ≠ charge; can backfill Gold if Gold table is empty. | Not mentioned in snapshot; if available, higher fidelity than Gold CSV. |
| **Register (Patient Payments)** | Patient copays, deductibles, self-pay | **Patient portion estimates** only; useless for insurance TP. | Available but irrelevant for insurance estimation. |
| **SoftDent Ledger (Charges)** | Billed fees, adjustments, contractual write-offs | **Noisy proxy** for payments; includes non-contractual adjustments and staff errors. Current 46-cell catalog is derived from this—insufficient for reliable TP. | **Current state** (sparse, high variance). |

**Industry Truth**: Without Gold or ERA, you are estimating based on what the office *billed*, not what the carrier *paid*. In SoftDent, staff often post “adjustments” that mask actual payments (e.g., posting a contractual write-off as a “credit” instead of linking it to the insurance payment). This creates phantom $0 payment lines in the ledger. Only Gold (actual payment transactions) or ERA (remittance detail) can provide honest, usable cells for the InsCo×ADA matrix.

## 6. Treatment-planning honesty doctrine (empty≠$0; when % vs $; secondary ins)

- **empty ≠ $0** (HAL-10603 shipped): A missing cell in the InsCo×ADA matrix must return `None` or “Insufficient Data,” never `$0.00`. Displaying $0 implies the procedure is not covered, which is a false negative.
- **Percentage vs. Dollar Estimates**:
  - Use **dollar estimates** only when Gold/ERA provides n≥30 payment lines for that cell with CV (coefficient of variation) < 0.25.
  - Use **percentage estimates** (e.g., “50% of UCR”) when 10 ≤ n < 30 or when the carrier is Medicaid (fixed schedule, but ledger noise requires % smoothing).
  - Return **null** when n < 10.
- **Secondary Insurance**: SoftDent does not reliably store Coordination of Benefits (COB) rules (standard vs. non-duplication). Therefore:
  - TP estimates should **default to Primary only**.
  - Secondary estimate displays as “Pending COB” or adds a probabilistic range (e.g., “0–80% of remaining balance”) but never a hard dollar amount without Gold history showing that specific COB sequence.
- **Source Tagging**: Every estimate must carry a source tag (`viaGold`, `viaAlias`, `viaLedger`, `insufficient`) so staff know the confidence level.

## 7. Recommended NEXT package (ONE) — name, why now, effort, validation gate

**HAL-10605: Gold Payment Line CSV Ingest & Settlement Matrix Hydration**

**Why Now**:  
HAL-10604 exhausted the low-hanging alias fruit (136 accepted). The remaining 77 are honest NONEs that aliases cannot solve. The only way to expand the usable InsCo×ADA catalog beyond the current 46 sparse cells is to inject ground-truth payment data. Without Gold, TP remains a probabilistic guess; with Gold, it becomes a financial forecast.

**Effort**: **Medium**  
- Export: SoftDent `sd_insurance_payment_lines` → CSV (office IT task, 30 min).  
- Transform: Map SoftDent InsCo IDs to spine via existing accepted aliases (2–3 hrs).  
- Load: Aggregate to `settlement_cell` table (InsCo×ADA×AvgPaid×Count) (2 hrs).  
- Validation: Honesty CI regression tests (1 hr).

**Validation Gate**:  
- [ ] Office delivers `sd_insurance_payment_lines` CSV with ≥1,000 rows covering ≥12 months.  
- [ ] Post-ingest, the InsCo×ADA catalog shows ≥200 cells with n≥10 (vs. current 46).  
- [ ] Honesty CI passes: `emptyIsNotZero` remains true; no synthetic payment lines invented.  
- [ ] Spot-check: Compare 10 random Gold-derived averages against paper EOBs; variance < 5%.

## 8. Runner-ups (2–3)

1. **HAL-10606: Secondary COB Estimation Logic**  
   *Why not now*: Requires primary Gold data to be reliable first; blocked by 10605.

2. **HAL-10606: Address-Field Mining for Remaining 77**  
   *Why not now*: High engineering effort (regex/NER on SoftDent address lines) to salvage maybe 5–10 additional aliases; lower ROI than Gold ingestion.

3. **HAL-10606: Delta Dental & BCBS State Defaulting (KS/Midwest)**  
   *Why not now*: Geography helps, but many “Delta Dental” entries without state are actually ASO shells or discount plans; risk of false positive is high without Gold confirmation.

## 9. What NOT to do

- **Over-match aliases**: Do not force-match the 77 rejected (e.g., guessing “Ahc” is “Aetna” or “Cna” is “CIGNA”). Prefer NONE.
- **Invent Gold payment lines**: Do not synthetic-populate `sd_insurance_payment_lines` with ledger charges or averages; empty ≠ $0.
- **SoftDent write-back**: Never write TP estimates back into SoftDent’s Treatment Plan module or Ledger; the program is consult/analytics only.
- **Auto-accept MEDIUM aliases**: Coventry → Aetna remains pending; do not upgrade to accepted without Gold evidence showing the settlement actually routes to Aetna financials.
- **Use ledger charges as Gold**: Do not treat “charge minus adjustment” as a payment; this double-counts write-offs and staff errors.

## 10. Acceptance criteria if operator says proceed on §7

- [ ] **Data Delivery**: `gold_payment_lines.csv` exported from SoftDent with columns: `InsuranceCompanyID`, `ADA_Code`, `PaymentAmount`, `PaymentDate`, `ClaimID`, `PatientID`.
- [ ] **Ingestion**: CSV loaded into `insurance_payment_line` table; duplicate ClaimID/LineItem checks pass (idempotency).
- [ ] **Spine Linkage**: ≥90% of payment lines map to accepted spine carriers via existing aliases; orphans are flagged, not forced.
- [ ] **Matrix Hydration**: New table `settlement_matrix` created with schema `(spine_carrier, ada_code, avg_paid, n_payments, std_dev, last_updated)`; ≥200 distinct (carrier, code) pairs with n≥10.
- [ ] **Honesty Preservation**: Honesty CI (HAL-10603) passes; nulls in matrix remain null (no zero-filling).
- [ ] **Source Provenance**: TP lookup logic updated to prefer `viaGold` > `viaAlias` > `viaLedger`; UI displays source tag.
- [ ] **Performance**: Aggregation query completes in <2s for typical GP procedure code set (D0100–D9999).

## 11. Executive Summary (7 bullets max)

- **Alias exhaustion**: 136/215 carriers mapped; remaining 77 are honest NONEs (TPAs, employers, junk) and should not be force-matched.
- **Two new HIGH aliases viable**: `Great-west` → CIGNA DENTAL; `Kanawha` → HUMANA DENTAL (acquisitions finalized >15 years ago).
- **Gold is the bottleneck**: Only 46 usable InsCo×ADA cells exist because `sd_insurance_payment_lines` is empty; ledger-based estimates are too noisy for reliable TP.
- **Next package**: HAL-10605 ingests Gold CSV to hydrate the settlement matrix with actual paid amounts, expanding usable cells from 46 to 200+.
- **Geography matters**: KS/Midwest offices predominantly use BCBS of KS, Delta Dental of KS, Aetna, Cigna, and MetLife; Gold data will confirm state-specific fee schedules.
- **Honesty first**: Maintain `empty≠$0`; never write back to SoftDent; never invent payment lines.
- **Secondary ins**: Blocked until Gold provides primary estimates; do not guess COB rules.

## 12. Approval checklist

- [ ] Operator confirms access to SoftDent `sd_insurance_payment_lines` export (Gold CSV).
- [ ] Acceptance criteria §10 agreed (especially n≥10 threshold and no zero-filling).
- [ ] Explicit confirmation that **Coventry remains MEDIUM pending** (no auto-accept).
- [ ] Explicit confirmation that **77 rejected remain NONE** (no force-match of Ahc, Bma, TPAs, or employers).
- [ ] Confirmation that program remains **read-only** (no SoftDent write-back).
- [ ] Build ID `hal-10605` assigned for tracking.