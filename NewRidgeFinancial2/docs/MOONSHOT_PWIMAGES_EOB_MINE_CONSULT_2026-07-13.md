# Moonshot AI — PWImages Dental Insurance EOB Mine (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10606  
**Script:** `scripts/run_moonshot_pwimages_eob_mine_consult.py`  
**Mine:** `NewRidgeFinancial2/docs/_pwimages_eob_mine/`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> we just mined c:\softdent\pwimages for all insurance eobs, ask moonshot ai what he wants to do with these in the program and consult

---

# Verdict
Warehouse the 15 scanned remittance EOBs for audit-only reference and ingest the 2,270 eligibility/benefits documents to resolve carrier aliases and extract plan parameters (deductibles, frequencies, annual maxima) for the TP estimator, but explicitly **do not** wire any OCR-extracted dollar amounts into the settlement matrix or Gold CSV.

## 0. Operator Intent (verbatim)
> "we just mined c:\softdent\pwimages for all insurance eobs, ask moonshot ai what he wants to do with these in the program and consult"

## 1. Mine triage (what we actually have vs what staff call "EOBs")
- **Remittance EOBs (actual payment explanation):** 15 files total (8 high-confidence REMITTANCE_EOB, 7 low-confidence REMITTANCE_EOB_CANDIDATE). These contain claim payments, patient responsibility, and check/EFT traces.
- **Eligibility/Benefits (plan design documents):** 2,270 HTM/JPG files. These are portal downloads, faxed benefit summaries, and plan booklets showing coverage percentages, deductibles, waiting periods, and frequencies—not payment history. Staff often label these "EOBs" incorrectly.
- **Insurance Related:** 1,338 mixed documents (letters, authorization notices, card images).
- **Insurance Cards:** 4 images.
- **Reality check:** The corpus is overwhelmingly plan documentation (92% eligibility/benefits) rather than remittance data. The 15 remittance files are statistically insufficient for ML training or reliable OCR entity extraction.

## 2. Program value by document class (remittance / eligibility / card / other)
| Class | Count | NR2 Value | Risk |
|-------|-------|-----------|------|
| **Remittance EOBs** | 15 | Audit-trail reference only; manual lookup for denied claim appeals. | **High:** OCR $ extraction is unreliable at this volume; inventing settlement dollars violates honesty doctrine when Gold CSV is absent. |
| **Eligibility/Benefits** | 2,270 | **High:** Carrier name string extraction to resolve the 215 carrier aliases; plan parameter extraction (deductibles, annual max, frequencies, waiting periods) to feed TP estimator logic without requiring fee schedules. | Low: No monetary settlement data; read-only enrichment. |
| **Insurance Cards** | 4 | Minimal; member ID validation possible but low ROI given existing alias table. | Low |
| **Insurance Related** | 1,338 | Moderate: May contain narrative denial reasons or authorization codes useful for appeals workflow. | Medium: Unstructured text, variable value. |

## 3. Recommended NEXT package (ONE) — name, why now, effort, real files, gate
**HAL-10607: PWImages Eligibility Benefits Alias & Plan Parameter Bridge**

- **What:** Ingest the 2,270 eligibility/benefits documents to (a) extract carrier name strings and fuzzy-match them to the 215 existing carrier aliases, improving the InsCo×ADA spine coverage; (b) parse plan parameters (deductibles, preventive/basic/major percentages, annual maximums, frequency limits) into a staging table for TP estimator consumption.
- **Why now:** The TP estimator currently operates on ~46 usable InsCo×ADA cells due to sparse alias resolution. The 2,270 eligibility corpus provides the raw text needed to map ambiguous scanned carrier names (e.g., "Cigna Dental Health of Kansas") to normalized SoftDent InsCo IDs without waiting for Gold CSV. This is non-monetary data, so honesty doctrine is preserved.
- **Effort:** Medium. Requires OCR text extraction (already done), regex/heuristic benefit parsing, and fuzzy matching against the alias table. No SoftDent write-back; read-only staging tables.
- **Real files:** `eob_mine_all.json` (2,270 ELIGIBILITY_BENEFITS rows) → `staging_eligibility_parameters` table.
- **Gate:** Operator must confirm that no OCR-derived dollar amounts from the 15 remittance files will be ingested into the settlement matrix.

## 4. How this relates to Gold CSV and ERA/835 (complement vs substitute)
- **Complement, not substitute:** 
  - **Gold CSV / ERA 835:** Provide ground-truth actual paid amounts (settlement reality). These remain the **only** acceptable sources for populating `sd_insurance_payment_lines` and the InsCo×ADA settlement matrix.
  - **HAL-10607 (Eligibility Corpus):** Provides **plan design** (benefit structure) and **carrier identity** (alias resolution). This improves TP estimate accuracy by knowing that a plan pays 80% on D2740, but it does not claim to know the actual paid amount until Gold/835 arrives.
- **Substitution prohibited:** Under no circumstances may the 15 scanned remittance EOBs substitute for missing Gold CSV data. They are warehoused for staff visual reference only.

## 5. Honesty / safety rules if any OCR $ ever surfaces in UI
1. **Empty ≠ $0:** If OCR fails to read an amount, the field remains `NULL` in the database, never zero.
2. **No write-back:** OCR-derived data never writes to SoftDent tables, Register collections, or Gold CSV.
3. **Visual warning:** Any UI displaying OCR-extracted monetary values must carry a red banner: **"UNVERIFIED SCANNED ESTIMATE — DO NOT POST. AWAIT GOLD CSV OR ERA 835 FOR SETTLEMENT TRUTH."**
4. **Override requirement:** Users cannot "confirm" OCR $ to promote them to financial reports; only Gold/835 data flows to HAL financial truth layers.
5. **Audit logging:** All OCR extractions logged with confidence scores; low-confidence fields hidden from UI.

## 6. Runner-ups (2–3)
1. **HAL-10608: OCR Remittance Auto-Posting Engine** — *Rejected:* Only 15 samples, insufficient for training; violates honesty doctrine by inventing settlement dollars without Gold/835 ground truth.
2. **HAL-10609: Insurance Card Vision Extract** — *Rejected:* Only 4 card images; minimal value compared to alias table already in place.
3. **HAL-10610: Document Classifier Retraining** — *Rejected:* Requires labeled training set; 15 remittance samples insufficient for statistically significant validation.

## 7. What NOT to do
- **Do not** build an automated pipeline that extracts "Amount Paid" or "Patient Responsibility" from the 15 remittance EOBs and injects them into `sd_insurance_payment_lines` or the settlement matrix.
- **Do not** allow staff to "match" the 15 scanned remittance EOBs to open claims and manually key OCR dollars into HAL as a temporary fix for missing Gold CSV.
- **Do not** use the 15 remittance samples to train a vision model for document classification; the sample size is statistically meaningless.
- **Do not** pause Gold CSV procurement or ERA 835 onboarding because "we have scanned EOBs now."

## 8. Acceptance criteria if operator says proceed on §3
- [ ] 2,270 eligibility/benefits documents parsed for carrier name strings with ≥80% fuzzy-match success rate against existing 215-alias table.
- [ ] Plan parameters extracted into `staging_eligibility_parameters` (deductibles, frequencies, waiting periods, coverage percentages) with confidence scoring; low-confidence extractions flagged for manual review.
- [ ] 15 remittance EOBs stored in blob storage (`remittance_eobs/`) with indexed account links but **no** extracted dollar fields in the database schema.
- [ ] UI view for warehoused remittances includes mandatory honesty banner (see §5) and read-only access.
- [ ] Gold CSV procurement and ERA 835 integration remain prioritized in parallel roadmap; HAL-10607 does not replace them.
- [ ] No SoftDent write-back occurs; all changes are in NR2 analytical layer only.

## 9. Executive Summary (7 bullets max)
- Mine discovered 2,270 plan documents vs. only 15 actual payment remittances (statistically insignificant).
- OCR dollar extraction from remittances is prohibited by honesty doctrine given zero Gold CSV baseline.
- Value concentrates in eligibility corpus: carrier alias resolution and plan benefit extraction for TP estimates.
- HAL-10607 targets eligibility ingest only, leaving remittances in read-only audit warehouse.
- Maintains strict firewall between scanned plan design (allowed) and scanned settlement dollars (prohibited).
- Gold CSV and ERA 835 remain the sole authorized sources for settlement truth.
- Build proceeds only with explicit operator acknowledgment that OCR $ will never enter financial reports.

## 10. Approval checklist
- [ ] Operator acknowledges that the 15 remittance EOBs are for visual audit only and will not be used to populate missing payment data.
- [ ] Operator confirms priority of Gold CSV procurement is unchanged.
- [ ] Acceptance threshold for carrier alias fuzzy-matching (≥80%) agreed.
- [ ] Schema for `staging_eligibility_parameters` (plan benefits) approved by TP estimator module owner.
- [ ] Resource allocated for manual review of low-confidence plan parameter extractions (~10% of 2,270 expected).