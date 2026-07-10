# SoftDent ADA × Payer Treatment Planning — Applied

**Date:** 2026-07-10  
**Build:** **hal-10400**  
**Consult:** `MOONSHOT_SOFTDENT_ADA_PAYER_TX_CONSULT_2026-07-10.md`  
**Status:** Applied after operator proceed

## What landed

### Insurance payment lines (MUST)
- New `softdent_treatment_planning.py`
  - Ingests newest `insurance_payments*.csv` / `insurance_payment_analysis*.csv` from
    `C:\SoftDentFinancialExports` (also SoftDentReportExports / SoftDent import dir)
  - Flexible header aliases: InsCo, ADA/CDT, submitted, allowed, paid, write-off, patient portion, claim/check #
  - Upserts **line items** into NR2-owned `sd_insurance_payment_lines` (importer `insurance_payment_distribution` is aggregate-only)
  - Optionally hydrates empty importer `insurance_payment_distribution` from InsCo rollups

### Procedure code crosswalk (SHOULD)
- Ingests `procedure_codes*.csv` → `sd_procedure_code_reference` (`internal_code` → `ada_cdt_code`)
- Heuristic normalize: SoftDent `111000` → `D1110`, bare `0274` → `D0274`

### PHI-safe estimates
- Rebuilds `treatment_planning_estimates` (InsCo × ADA averages, **no patient/DOS/claim PHI**)
- Skips generic payer label `"Insurance"`
- HAL answers only when `sample_size >= 10`; otherwise honest insufficient-data reply

### Sync + HAL
- `import_sync.py` runs `run_treatment_planning_ingest()` after transaction/CSV extract → `softdent.treatmentPlanning`
- Board-actions: “How much will Delta Dental typically pay for D0274?” + “Treatment planning data status”
- API: `GET /api/apex/treatment-planning/status`, `GET /api/apex/treatment-planning/estimate?payer=&ada=`
- HAL chips: **Tx plan data status**, **Delta pay for D0274?**

## Operator export steps (required for live estimates)

1. SoftDent → Reports → Insurance → **Insurance Payment Analysis** (24 months) → CSV  
2. Optional: Procedure Code Listing → CSV  
3. Drop as `C:\SoftDentFinancialExports\insurance_payments_YYYYMMDD.csv`  
   (+ `procedure_codes_YYYYMMDD.csv`)  
4. Sync imports (or restart sync path)

## Tests
- `test_softdent_treatment_planning.py` — normalize, parse query, ingest, n≥10 estimate, insufficient sample, crosswalk

## Honesty / limits
- Does not invent allowed/paid amounts when CSV absent
- Estimates are historical averages — not benefits guarantees
- Current live `transactions_for_period` still lacks payer/ADA join; this pack does **not** claim that lane is fixed

## Files
- `softdent_treatment_planning.py` (new)
- `test_softdent_treatment_planning.py` (new)
- `import_sync.py` — treatmentPlanning hook
- `apex_backend.py` — board-actions + API + BUILD_ID **hal-10400**
- `site/apex-core.js` — chips
- `nr2-build.json` / `site/nr2-build.json` → **hal-10400**
