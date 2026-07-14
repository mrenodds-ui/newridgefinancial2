# HAL-10606 — SoftDent Gold CSV drop facilitation (applied)

**Date:** 2026-07-13  
**Consult:** `MOONSHOT_WHATS_NEXT_AFTER_HAL10605_2026-07-13.md`  
**Operator:** proceed  
**BUILD_ID:** `hal-10606`

## Verdict applied

OPS facilitation so HAL-10605 `settlement_matrix` can hydrate when a **real** insurance payment line-item CSV lands. Does **not** invent gold. SoftDent v19 Print Preview honesty preserved.

## What shipped

| Piece | Location |
|-------|----------|
| Module | `softdent_gold_drop_facilitation_hal10606.py` |
| Staff briefing + path writable check | `staff_briefing()`, `verify_export_path_writable()` |
| Matrix acceptance gate | ties to HAL-10605 `settlement_matrix_status` |
| Runner | `run_ops_10606_gold_drop_facilitation()` (wraps 10589 OPS) |
| Widget | `softdent-gold-drop-facilitation-hal10606` |
| API | `GET/POST /api/apex/gold-drop-facilitation/status|run` |
| Sync | `import_sync.py` records facilitation + warns while gate unmet |
| Tests | `test_hal10606_gold_drop_facilitation.py` |
| Live report | `C:\SoftDentFinancialExports\gold_drop_facilitation_hal10606_*.{json,md}` |

## SoftDent reality (unchanged)

- v19.1.4 has **no** menu named Insurance Payment Analysis  
- Insurance Income / related → **Print Preview only** (≠ gold lines)  
- Drop real line-item CSV as `insurance_payments_YYYYMMDD.csv` under `C:\SoftDentFinancialExports\` → Sync  

## Live after apply

| Check | Result |
|-------|--------|
| exportPath writable | yes |
| gapCode | `GOLD_CSV_MISSING` |
| paymentLines / matrixCells | `0` / `0` |
| acceptanceGateMet | **false** (blocked on CSV drop) |
| inventedGold | **false** |

## Honesty

empty ≠ $0 · no SoftDent write-back · Print Preview ≠ `sd_insurance_payment_lines` · Coventry still pending · 75 rejected untouched
