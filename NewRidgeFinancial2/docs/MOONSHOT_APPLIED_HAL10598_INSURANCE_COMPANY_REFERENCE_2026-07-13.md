# HAL-10598 — SoftDent insurance company master CSV (applied)

**Date:** 2026-07-13  
**Source:** `C:\New folder\artifacts\softdent_insurance_companies_2026-06-06.csv`  
**BUILD_ID:** `hal-10598`

## What shipped

| Piece | Location |
|-------|----------|
| Ingest module | `softdent_insurance_company_reference.py` |
| CLI | `scripts/import_softdent_insurance_companies_csv.py` |
| Stable copy | `C:\SoftDentFinancialExports\softdent_insurance_companies.csv` |
| Catalog status | `companyReference` on InsCo×ADA catalog widget/status |
| Tests | `test_hal10598_insurance_company_reference.py` |

## Live load

- **446** companies total  
- **215** likely_active  
- **228** discontinued  
- Spine overlap with likely_active: **71**  
- Likely_active not yet in settlement spine: **144** (name variants / no ledger episodes)

## Honesty

Master list only — does **not** invent InsCo×ADA dollars or clear `insufficient` without settlements. empty ≠ $0.
