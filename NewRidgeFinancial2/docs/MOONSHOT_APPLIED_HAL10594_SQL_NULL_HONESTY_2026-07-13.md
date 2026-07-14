# HAL-10594 / sql-null-honesty (applied)

**Date:** 2026-07-13  
**Prior consult:** `MOONSHOT_MONEY_HARDENING_CONSULT_2026-07-13.md`  
**Operator:** `proceed`  
**BUILD_ID:** `hal-10594`

## What shipped

| Piece | Location |
|-------|----------|
| NULL-preserving ledger SUM | `sum_ledger_code2_payments` — CASE WHEN COUNT(cash)+COUNT("check")+COUNT(credit)>0 |
| NULL-preserving carrier rows | `sum_ledger_code2_by_carrier` — per-row CASE; skip NULL amounts |
| Inputs-only fingerprint | `record_fingerprint` (no clamped/delta/result in hash) |
| Collision fail-fast | UNIQUE INDEX + pre-insert check → `record_fingerprint_collision` |
| History SQL notes | `docs/m_10593_recon_variance_history.sql` (JSON floats vs Decimal variance) |
| Tests | `test_hal10594_sql_null_honesty.py` (`test_ledger_all_null_returns_none`) |

## Behavior

- Code-2 rows with all-null `cash`/`check`/`credit` → `ledgerTotal: null` (not `0.0`).
- Carrier breakdown never invents zero-amount `(unmapped)` from NULL amounts.
- History append fails fast on duplicate inputs; no silent overwrite.
- Flag only — no SoftDent write-back, no gold invent. empty != $0.

## Honesty

Restores empty≠$0 at the SQL aggregation layer after Decimal/audit hardening (`8b2befa`).
