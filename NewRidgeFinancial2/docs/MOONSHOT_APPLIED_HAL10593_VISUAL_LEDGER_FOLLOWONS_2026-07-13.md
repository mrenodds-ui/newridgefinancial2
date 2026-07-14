# HAL-10593 / HON-003 — Visual×Ledger Follow-ons (applied)

**Date:** 2026-07-13  
**Prior consult:** `MOONSHOT_WHATS_NEXT_AFTER_HAL10592_2026-07-13.md`  
**Operator:** `proceed`  
**BUILD_ID:** `hal-10593`

## What shipped

| Piece | Location |
|-------|----------|
| Carrier breakdown | `sum_ledger_code2_by_carrier` — primary InsCo map, top 5, codes only |
| Period clamp | `clamp_ledger_to_audit_period` → `clampedLedgerTotal` when `scopeMismatch` |
| History | `recon_variance_history` + `docs/m_10593_recon_variance_history.sql` |
| Widget | carrierBreakdown, clampedLedgerTotal fields |
| API | `GET /api/apex/reconciliation/visual-ledger/history?months=` |
| CLI | `--carrier-breakdown`, `--show-history-months=N` |
| Tests | `test_hal10593_visual_ledger_recon.py` |

## Behavior

- Primary ledger window = **requested** period when provided; clamp re-queries **audit** `dateRange` on mismatch.
- Carrier breakdown sums code-2 amounts by primary insurance name (no PHI).
- History stores aggregates only; `triggers_gold_ingest=0`.
- Flag only — no SoftDent write-back, no gold invent. empty != $0.

## Honesty

Builds on HAL-10591/10592. `gapCode` may remain `GOLD_CSV_MISSING`; `paymentLines` stays honest.
