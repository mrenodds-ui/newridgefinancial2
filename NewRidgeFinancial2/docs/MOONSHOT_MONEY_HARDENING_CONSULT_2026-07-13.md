# Moonshot AI — Visual-Ledger Decimal/Audit Hardening Consult (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10593  
**Prior:** money hardening (`8b2befa`) on HAL-10593  
**Script:** `scripts/run_moonshot_money_hardening_consult.py`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> run what you just did through moonshot ai for a consult

---

# Verdict
The hardening is **architecturally adequate** for cent-safe arithmetic and audit immutability, but **not production-safe** due to a critical SQL-layer violation of the empty≠$0 policy; recommend hotfix before stress testing.

## 0. Operator Intent (verbatim)
> run what you just did through moonshot ai for a consult

## 1. What the hardening got right
- **Decimal quantization** (`money_cents.py:TWOPLACES` with `ROUND_HALF_EVEN`) eliminates binary-float drift in variance calculations.
- **Empty≠$0 enforcement** at Python boundaries (`to_money` returns `None` for empty/missing; `is_empty_money` guards in `classify_variance`).
- **Cent-exact MATCH** uses `Decimal` equality rather than float tolerance, preventing false positives on rounding edges.
- **Tamper-evident history** via `input_fingerprint` (SHA-256) and `money_scale` column documentation.
- **Flag-only integrity** — no SoftDent write-back, no synthetic gold payment lines (`triggers_gold_ingest` hardcoded `0`).
- **SQLite concurrency** — `BEGIN IMMEDIATE` + `busy_timeout` prevents WAL contention during history inserts.

## 2. Residual bugs / risks (severity + file:symbol)
| Severity | Location | Issue |
|----------|----------|-------|
| **CRITICAL** | `softdent_visual_ledger_recon.py:sum_ledger_code2_payments` (SQL) | `COALESCE(cash,0)+COALESCE("check",0)+COALESCE(credit,0)` collapses all-NULL rows to `0` instead of `NULL`, violating empty≠$0 at the aggregation layer. If the database contains code-2 rows with all-null amounts, the ledger reports `$0.00` (false positive) instead of `None` (honest missing data). |
| **HIGH** | `money_cents.py:money_to_api` | IEEE-754 double cannot represent all cent values exactly above 2^53 cents (~$90 trillion). While dental claims rarely hit this, the bridge is **not** bijective for arbitrary Decimal → float → Decimal round-trips, creating a compliance gap for high-value orthodontic ledgers. |
| **MEDIUM** | `softdent_visual_ledger_recon.py:ensure_recon_variance_history_schema` | `input_fingerprint` includes computed outputs (`clamped`, `delta`, `result`), defeating its purpose as a reproducibility key; same inputs with different bugs will hash differently, hiding non-determinism. |
| **MEDIUM** | `softdent_visual_ledger_recon.py:_select_visual_audit` | Code snippet truncated (ends mid-function); if production code matches snippet, the function is incomplete and will raise `IndentationError` or `SyntaxError`. |

## 3. Compliance / audit-trail gaps still open
- **No chain of custody**: History rows lack `prev_fingerprint` or Merkle link; records can be deleted or reordered without cryptographic detection.
- **No actor attribution**: `user_id`/`session_hash` absent from history schema — cannot prove who triggered the reconciliation.
- **No immutability guarantee**: SQLite `DELETE`/`UPDATE` still permitted on `recon_variance_history`; append-only enforcement missing.
- **Float serialization risk**: JSON consumers may parse `100.0` as `99.999999999` depending on parser, breaking external audit verification.

## 4. Recommended NEXT (one package only — or NONE if hold)
**Package `hal-10594 sql-null-honesty`**  
Replace the `COALESCE` sums in `sum_ledger_code2_payments` and `sum_ledger_code2_by_carrier` with NULL-preserving aggregation:
```sql
CASE 
  WHEN COUNT(cash) + COUNT("check") + COUNT(credit) > 0 
  THEN SUM(COALESCE(cash,0) + COALESCE("check",0) + COALESCE(credit,0))
  ELSE NULL 
END
```
This restores empty≠$0 for all-null row sets. **Hold** `hal-10593` production traffic until this ships.

## 5. What NOT to redo
- **Do not** revert to `float` for internal variance math (keep `Decimal` throughout).
- **Do not** add patient-level PHI (account numbers, names) to `recon_variance_history`; keep aggregates only.
- **Do not** implement SoftDent write-back or synthetic gold line insertion (remain flag-only).
- **Do not** change `ROUND_HALF_EVEN` to `ROUND_HALF_UP`; banker's rounding is correct for GAAP/IFRS compliance.
- **Do not** add complex ORM/SQLAlchemy; keep raw SQLite with busy_timeout for determinism.

## 6. Acceptance checks if operator says proceed on your NEXT
- [ ] SQL query returns `ledgerTotal: null` (not `0.0`) when `sd_account_transactions` has code-2 rows but all `cash`/`check`/`credit` are NULL.
- [ ] `money_to_api(Decimal("999999.99"))` serializes to JSON and parses back to exactly `999999.99` in Python, JavaScript, and C# float parsers.
- [ ] History insert fails fast (SQLite constraint) if `input_fingerprint` collision detected on same inputs (prevents silent overwrites).
- [ ] Carrier breakdown correctly skips unmapped carriers when `amt` is NULL (no zero-amount "(unmapped)" lines).

## 7. Approval checklist
- [ ] `hal-10594` diff shows `COALESCE` moved inside conditional `CASE` or equivalent NULL-preserving logic.
- [ ] Unit test added: `test_ledger_all_null_returns_none` — inserts code-2 row with NULL amounts, asserts `ledgerTotal is None`.
- [ ] `input_fingerprint` renamed to `record_fingerprint` OR outputs removed from hash (inputs only).
- [ ] Documentation updated: `docs/m_10593_recon_variance_history.sql` notes that `visual_total`/`ledger_total` are JSON floats (approximate) while `variance_dollars` is derived from Decimal.