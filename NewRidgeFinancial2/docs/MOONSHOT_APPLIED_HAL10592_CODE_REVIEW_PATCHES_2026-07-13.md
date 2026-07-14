# HAL-10592 code-review patches (applied — Moonshot fix order, no deviation)

**Date:** 2026-07-13  
**Prior:** `MOONSHOT_HAL10592_CODE_REVIEW_2026-07-13.md`  
**Operator:** `proceed exactly as moonshot ai directed with[out] deviation`  
**BUILD_ID:** `hal-10592` (unchanged; patch on package)

## Fix order applied

1. **Widget return** — `visual_ledger_recon_widget` returns complete dict with `ok` / `result` (was already complete; reinforced).
2. **Calendar validation** — `parse_date_range` wraps `date()` / `fromisoformat` in `try/except ValueError` → `(None, None)`.
3. **SQL safety** — `sum_ledger_code2_payments` builds `IN (?,?,…)` via string concat of `?` placeholders only; no f-string SQL; values stay bound params.
4. **Precision** — MATCH uses `math.isclose(v, l, abs_tol=0.005)`.
5. **scopeMismatch** — set when audit `dateRange` bounds ≠ requested period bounds; surfaced on recon + widget.
6. **Perf** — removed `TRIM(procedure)` (trusted clean codes at ingest; index-friendly).

## Acceptance (Moonshot §7)

- Widget import/call: no `NameError`
- `parse_date_range("2026-02-30")` / `"2026-13"` → `(None, None)`
- `classify_variance(None, 0.0)` → `INSUFFICIENT_VISUAL`, `delta=None`
- `classify_variance(0.0, 0.0)` → `MATCH`
- No f-string SQL / no `TRIM(procedure)` in sum helper
- End-to-end 100 vs 98 → `VARIANCE_WITHIN_TOLERANCE`
- `triggersGoldIngest` never `True`
