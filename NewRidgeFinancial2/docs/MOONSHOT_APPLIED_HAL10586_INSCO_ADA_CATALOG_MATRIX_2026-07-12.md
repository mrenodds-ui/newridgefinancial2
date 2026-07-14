# HAL-10586 — Full InsCo × ADA Catalog Matrix (applied)

**Date:** 2026-07-12  
**Prior consult:** `MOONSHOT_WHATS_NEXT_AFTER_HAL10585_2026-07-13.md`  
**Operator:** `proceed`

## What shipped

| Piece | Location |
|-------|----------|
| Catalog module | `softdent_insco_ada_catalog_matrix.py` |
| SoftDent widget | `softdent-insco-ada-catalog` |
| APIs | `GET /api/apex/insco-ada-catalog/status`, `GET /api/apex/insco-ada-catalog` |
| HAL intent | `policy:insco-ada-catalog-matrix` |
| Sync | `import_sync.py` → `inscoAdaCatalog` |
| Tests | `test_insco_ada_catalog_hal10586.py` |
| Export | `C:\SoftDentFinancialExports\insco_ada_catalog_matrix_*.{json,md}` |

## Behavior

- Lists **all** spine cells including **insufficient** (empty ≠ $0)
- Joins $ + %+/- from unified HAL-10585 spine
- Ledger CDT universe + uncovered CDTs (seen in TX, no 2/51 settlement cell)
- Exact usable floor preserved (no re-filtering of credible cells)
- Filters: `includeInsufficient`, `includeInferred`, `credibility`, `payer`, `ada`

## Honesty

No SoftDent write-back; insufficient never coerced to $0.00; gold path unchanged.
