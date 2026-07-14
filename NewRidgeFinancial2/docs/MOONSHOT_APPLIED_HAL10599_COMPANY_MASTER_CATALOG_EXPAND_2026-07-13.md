# HAL-10599 — SoftDent company master × ADA catalog expand (applied)

**Date:** 2026-07-13  
**Prior:** HAL-10598 company master load · HAL-10596 spine catalog CSV  
**BUILD_ID:** `hal-10599`

## Task completed

Staff asked for **all ADA codes × all insurance companies we take** (plus treatment-plan % variances).  
Spine-only catalog had **72** settlement carriers. SoftDent company master has **215** likely_active.

## What shipped

| Piece | Detail |
|-------|--------|
| Expand | `expand_catalog_rows_with_company_master` — likely_active ∪ spine × ledger∪spine ADA |
| Pad cells | `credibility=no_settlement`, null $ / null %, `source=company_master_no_spine` |
| Staff CSV | Full grid in `insco_ada_catalog_matrix_*.csv` + inbox stable CSV |
| Honesty | Does **not** invent dollars for companies/ADAs without ledger 2/51 |

## Live result (2026-07-13)

| Metric | Count |
|--------|------:|
| Spine cells (ledger $/%) | 2,274 |
| Staff grid cells | **30,024** |
| Companies (likely_active ∪ spine) | **216** |
| ADA universe (ledger ∪ spine) | **139** |
| no_settlement pad (null $) | 28,653 |
| Exact usable (unchanged) | 46 |

**CSV:** `C:\SoftDentFinancialExports\insco_ada_catalog_matrix_2026-07-13.csv`  
**Inbox:** `app_data\nr2\document_inbox\softdent\softdent_insco_ada_catalog_matrix.csv`
