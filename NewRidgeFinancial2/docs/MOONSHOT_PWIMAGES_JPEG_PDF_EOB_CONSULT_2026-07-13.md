# Moonshot AI — PWImages JPEG/PDF EOB Mine (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10607  
**Script:** `scripts/run_moonshot_pwimages_jpeg_pdf_eob_consult.py`  
**PWImages:** `C:\SoftDent\PWImages`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> have moonshot ai mine c:\softdent\pwimage for eob. most were either jpeg or pdf files and consult

---

# Verdict
STOP further JPEG/PDF OCR expansion; the PWImages remittance corpus is exhausted (16 files, 0.6% yield in Account lane, zero in PDF), and analytical honesty demands pivoting to Gold CSV / ERA 835 ingestion for settlement truth.

## 0. Operator Intent (verbatim)
have moonshot ai mine c:\softdent\pwimage for eob. most were either jpeg or pdf files and consult

## 1. JPEG / PDF reality check vs operator expectation
- **PDF Myth Busted**: All 201 PDFs are `Check-In_Package_*` administrative forms. **Zero remittance EOBs** exist in the PDF lane.
- **JPEG Reality**: True remittance EOBs live exclusively in `NonPatient\Account\*.JPG` (~2,641 files) and 5 Claim JPGs—not in Patient folders.
- **Patient JPGs (~88k)**: Located in `Patient\*\Other\*.JPG`; these are overwhelmingly intraoral photos, radiographs, and clinical scans. OCR here is ROI-poor (noise-to-signal prohibitive).
- **Yield Truth**: Prior Tesseract mine extracted only **16 remittance EOBs** from 2,646 candidate JPGs (0.6% hit rate), plus 2,276 eligibility HTMs.

## 2. Where remittance EOBs actually are in PWImages
- **Location**: `C:\SoftDent\PWImages\NonPatient\Account\*.JPG` (2,641 files) and scattered `Claim\*\*.JPG` (5 files).
- **Format**: Scanned JPEG images (600–1200 dpi typical), not PDF.
- **Volume**: 8 high-confidence REMITTANCE_EOB + 8 CANDIDATE = **16 total** warehoused in HAL-10607.
- **Already Captured**: HAL-10607 copied these 16 to `docs\_pwimages_eob_mine\remittance_eobs` with path metadata; **no OCR dollar extraction** was performed (honesty).

## 3. Recommended NEXT (ONE package) — name, why, effort, files, gate
**STOP — Do Not Ship Another JPEG/PDF OCR Package**

- **Name**: Explicit STOP on OCR expansion; pivot to **HAL-10608-GOLD-ERA-SETTLEMENT-HYDRATION**.
- **Why**: The PWImages remittance vein is statistically depleted. With 0.6% yield in Account JPGs and 0% in PDFs, mining the remaining 88k Patient JPGs is analytically irresponsible. The 16 existing remittance scans serve only as audit breadcrumbs; they cannot hydrate the InsCo×ADA settlement matrix. Gold CSV (`sd_insurance_payment_lines`) and ERA 835 contain structured, adjudicated, carrier-certified truth—scanned JPEGs do not.
- **Effort**: High (835 parsing, claim-to-payment matching, exception handling), but honest and scalable.
- **Files**: Zero additional PWImages files processed.
- **Gate**: Receipt of either (a) SoftDent Gold CSV export containing `sd_insurance_payment_lines`, or (b) ERA 835 enrollment credentials with top 10 carriers.

## 4. Relation to HAL-10607 / Gold CSV / ERA 835
- **HAL-10607 Scope**: Already warehoused the 16 remittance paths (no $) and ingested 2,276 eligibility HTMs with 93.4% fuzzy carrier matching.
- **HAL-10607 Limit**: Explicitly did **not** write OCR-extracted amounts to `settlement_matrix` or `sd_insurance_payment_lines`.
- **Gold CSV**: Remains the sole valid source for populating the InsCo×ADA spine with actual paid amounts (UCR/schedule realities).
- **ERA 835**: Industry-standard remittance; required for automated posting and true RCM automation. PWImages JPEGs are non-structured audit trails only—useful for denial appeals, useless for estimator training.

## 5. Honesty rules for any further JPEG/PDF OCR $
- **Empty ≠ $0**: Absence of extractable amount means `NULL`, not zero dollars.
- **No SoftDent Write-Back**: Never post OCR-extracted dollars to patient ledgers or payment tables.
- **No Gold Substitution**: Scanned EOBs cannot substitute for Gold CSV or ERA 835 in settlement workflows.
- **Banner Requirement**: Any UI display of OCR-derived $ must carry: *"UNVERIFIED SCANNED ESTIMATE — DO NOT POST. AWAIT GOLD CSV OR ERA 835 FOR SETTLEMENT TRUTH."*
- **Prefer NONE/Insufficient**: When OCR confidence is low or parsing ambiguous, return `NONE` rather than hallucinated figures.

## 6. Runner-ups (2–3)
1. **HAL-10608-ACCOUNT-JPG-DEEP-DIVE**: Re-process the 2,625 remaining Account JPGs with layout-aware OCR (table detection) to find missed remittances. **Rejected**: 0.6% base rate implies ~15 additional files max; engineering cost exceeds audit value.
2. **HAL-10608-PATIENT-JPG-SAMPLE**: Stratified sample of 1,000 Patient Other JPGs to test for insurance card/remittance presence. **Rejected**: 88,000 clinical scans; expected remittance yield <0.01%; computationally wasteful.
3. **HAL-10608-MHT-ELIGIBILITY-PARSE**: Extract structured data from 62,007 MHT Carestream eForms. **Rejected**: MHTs are consent/medical history forms, not remittance or eligibility; zero insurance value.

## 7. What NOT to do
- **Do not** claim that PDFs contain remittance EOBs (100% Check-In forms).
- **Do not** OCR the 88,000 Patient Other JPGs (clinical noise).
- **Do not** attempt to train an estimator model on 16 scanned remittance JPEGs (statistically invalid).
- **Do not** invent InsCo×ADA settlement rates by averaging OCR’d check amounts from scanned EOBs.
- **Do not** mutate the SoftDent database with OCR-extracted payment lines.
- **Do not** label eligibility benefit summaries (HTMs) as “EOBs” in the UI; they are plan design documents, not payment explanations.

## 8. Acceptance criteria if proceed on §3
If operator overrides this consult and mandates continued JPEG/PDF OCR:
- **Gate**: Demonstrate >5% remittance yield in a 100-file random sample of remaining Account JPGs.
- **Honesty Tag**: All outputs tagged with `source=pwimages_ocr_unverified` and excluded from `settlement_matrix`.
- **Limit**: Hard cap of 500 Account JPGs processed; abort if cumulative yield <2%.
- **PDF Exclusion**: PDF path remains blocked (known zero yield).
- **DB Firewall**: OCR pipeline physically prohibited from writing to `sd_insurance_payment_lines`, `payment_lines`, or `settlement_matrix`.

## 9. Executive Summary (7 bullets max)
- **PDFs are myth**: All 201 PDFs are Check-In forms; zero remittance EOBs exist in PDF.
- **Remittance JPEGs scarce**: Only 16 found in 2,646 Account/Claim JPGs (0.6% yield).
- **Patient JPGs are clinical**: 88k files are radiographs/photos; OCR is ROI-negative.
- **HAL-10607 complete**: Eligibility warehoused (93% fuzzy match), remittance paths captured.
- **Honest pivot required**: Settlement truth requires Gold CSV or ERA 835, not more scans.
- **Recommendation**: STOP OCR expansion; prioritize Gold CSV/835 ingestion.
- **Risk of continuation**: Violates honesty doctrine by risking fabricated settlement data from low-fidelity scans.

## 10. Approval checklist
- [ ] Operator acknowledges PDFs contain zero remittance EOBs.
- [ ] Operator acknowledges 16 remittance JPEGs are already warehoused in HAL-10607.
- [ ] Operator agrees to STOP further JPEG/PDF OCR for settlement purposes.
- [ ] Operator authorizes pivot to Gold CSV / ERA 835 ingestion as next package.
- [ ] Operator confirms understanding that empty OCR results ≠ $0.
- [ ] Operator confirms no SoftDent write-back of OCR dollars will occur.