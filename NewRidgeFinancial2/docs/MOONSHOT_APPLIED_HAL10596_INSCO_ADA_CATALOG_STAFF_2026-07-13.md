# HAL-10596 / insco-ada-catalog-staff (applied)

**Date:** 2026-07-13  
**Prior:** HAL-10586 catalog matrix  
**Operator:** plan — both phased (ledger catalog first)  
**BUILD_ID:** `hal-10596`

## What shipped

| Piece | Location |
|-------|----------|
| Rebuild CLI | `scripts/rebuild_insco_ada_catalog.py` (spine→$→%→matrix) |
| Full-cell CSV | `insco_ada_catalog_matrix_*.csv` + inbox `softdent_insco_ada_catalog_matrix.csv` |
| Cents fields | `paidMedianCents` / `writeOffMedianCents` / `billedAvgCents` |
| Widget / API | `csvPath`, `uncoveredCount`, `exactUsableCells` |
| HAL | catalog CSV path intent |
| Tests | `test_hal10596_insco_ada_catalog_staff.py` |

## Behavior

- Exports **all** spine cells including `insufficient` (empty ≠ $0).
- Float $ columns retained but marked deprecated; prefer *Cents.
- Does **not** invent gold payment lines from ledger.

## Honesty

Ledger-inferred only. `gapCode=GOLD_CSV_MISSING` until a real SoftDent line-item CSV appears (Phase 2 OPS).
