# HAL-10592 / HON-002 — Visual-Audit × Ledger Spine Reconciliation (applied)

**Date:** 2026-07-13  
**Prior consult:** `MOONSHOT_WHATS_NEXT_AFTER_HAL10591_2026-07-13.md`  
**Operator:** `proceed`  
**BUILD_ID:** `hal-10592`

## What shipped

| Piece | Location |
|-------|----------|
| Reconciler | `softdent_visual_ledger_recon.py` — period parse, code-2 ledger sum, variance classify |
| Widget | `softdent-visual-ledger-recon` |
| API | `GET /api/apex/reconciliation/visual-ledger/status?period=`, `POST .../run` |
| HAL | `policy:visual-ledger-recon` |
| Sync | `import_sync.py` → `softdent.visualLedgerRecon` |
| CLI | `scripts/audit_visual_ledger_variance.py` |
| Tests | `test_hal10592_visual_ledger_recon.py` |

## Behavior

- Compare Print Preview `lastPageAggregateTotal` (source `print_preview_visual`) to SoftDent ledger **code-2** payment sum for the same `dateRange`.
- Thresholds: **$5.00** absolute **or** **5%** — either within → tolerance; both exceeded → flag.
- Null visual or null ledger → `INSUFFICIENT_*` (never treated as `$0.00`).
- Alert only — `triggersGoldIngest=false`; does not create/modify `sd_insurance_payment_lines`.
- Live `gapCode` may remain `GOLD_CSV_MISSING`; `paymentLines` stays honest.

## Honesty

Builds on HAL-10591 `enforce_empty_not_zero`. No SoftDent write-back. Visual ≠ gold.
