# Moonshot AI — HAL-10592 Visual×Ledger Recon Code Review (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10592  
**Prior:** HAL-10592 (`2ababd5`)  
**Script:** `scripts/run_moonshot_hal10592_code_review_consult.py`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> Please review this code for bugs, optimization, and edge cases.

---

# Verdict
Ship-worthy with patches: the honesty gates and flag-only logic are correct, but `visual_ledger_recon_widget` is syntactically incomplete (ship-blocking), and `parse_date_range` lacks validation for invalid calendar dates (e.g., 2026-02-30). Fix these two and the SQL f-string style before merge.

## 1. Critical / High bugs
- **FILE: `softdent_visual_ledger_recon.py` — `visual_ledger_recon_widget` (line ~285)**
  - **Bug:** Function body ends with bare name `result` (no assignment, no return). This raises `NameError` at runtime or import failure.
  - **Fix:** Complete the function: `return {"ok": True, "result": r.get("result"), ...}` or remove if dead code.

- **FILE: `softdent_visual_ledger_recon.py` — `parse_date_range` (lines 48–70)**
  - **Bug:** Regex validates digit patterns but not calendar logic; `date(y, mo, 1)` will raise `ValueError` on "2026-13-01" or "2026-02-30", crashing the reconciler.
  - **Fix:** Wrap `date()` construction in `try/except ValueError: return None, None`.

- **FILE: `softdent_visual_ledger_recon.py` — `sum_ledger_code2_payments` (line ~93)**
  - **Bug:** SQL uses f-string interpolation for `placeholders`. While `INS_PAYMENT_CODES` is currently a constant, this pattern violates defense-in-depth and breaks if the constant ever contains non-literal content.
  - **Fix:** Build placeholders with `",".join("?" for _ in codes)` (already done) but do **not** use f-string on the SQL; pass `codes` as parameters. Since `codes` length varies, use query builder pattern or `sqlite3` parameterized `IN` clause support.

## 2. Medium bugs & edge cases
- **FILE: `softdent_visual_ledger_recon.py` — `reconcile_visual_vs_ledger` (period alignment)**
  - **Edge:** If `period_key="2026-06"` matches an audit row with range "2026-06-01..2026-07-15", the code uses the full row range (June–July) for the ledger sum, not strictly June. This creates a scope mismatch risk between visual aggregate and ledger sum.
  - **Fix:** Validate that parsed `start`/`end` exactly equals the requested period, or emit a `scopeMismatch` warning when the audit range exceeds the requested period.

- **FILE: `softdent_visual_ledger_recon.py` — `classify_variance` (line ~150)**
  - **Edge:** Floating-point epsilon `delta_abs < 0.005` is arbitrary; `100.00 - 99.995` rounds to `0.0` and yields `MATCH`, but `99.994` yields variance. Use `math.isclose` with `abs_tol=0.005` for explicit intent.

- **FILE: `softdent_visual_ledger_recon.py` — `sum_ledger_code2_payments` (SQL)**
  - **Perf:** `TRIM(procedure)` prevents index usage on large `sd_account_transactions` tables. If data is clean, remove `TRIM`; if not, create a functional index or clean on ingestion.

- **FILE: `softdent_visual_ledger_recon.py` — `reconcile_visual_vs_ledger` (early return)**
  - **Edge:** When `is_empty_money(visual_raw)` is true, the function returns before fetching `ledger`, so the output lacks `ledgerTotal` context. This is honest (don’t compare empty), but operators may want to see that ledger *was* available. Consider populating `ledger` before the early return for observability while keeping `comparison.result = INSUFFICIENT_VISUAL`.

## 3. Optimization opportunities
- **SQL column function:** Remove `COALESCE(cash,0)+COALESCE("check",0)+COALESCE(credit,0)` if schema guarantees non-null, or store pre-computed payment total to avoid per-row function evaluation.
- **Connection lifecycle:** `sum_ledger_code2_payments` opens/closes SQLite per call. Use connection pool or pass `conn` handle for batch ops.
- **Redundant date parsing:** `parse_date_range` is called twice on the same row (once in selection loop, once implicitly). Cache parsed tuples in the candidate dict.

## 4. Honesty / policy risks (empty≠$0, visual≠gold)
- **Risk:** `classify_variance` uses `parse_money_or_empty` which relies on `is_empty_money`. In `ui_honesty_policy.py`, string values like `"0"` or `"$0.00"` are treated as empty (honest ambiguity), but if SoftDent ever emits explicit string `"0.00"` for a true zero, it will be treated as missing, potentially hiding a valid MATCH.
  - **Mitigation:** Document that visual audit must emit numeric `0.0` or `0` for true zeros, not strings.

- **Risk:** Scope mismatch between Print Preview (which may include write-offs, refunds, or prior-period adjustments depending on SoftDent’s filter) and `sd_account_transactions` code-2 sum (service_date filtered) is not flagged. A 10% variance could be legitimate data scope difference rather than data quality issues.
  - **Mitigation:** Add `scopeWarning` field to output when `reportType` != "InsuranceIncome" or when date range spans multiple months, alerting operators that variance may be expected.

- **Visual≠Gold:** Correctly enforced via `SOURCE_PRINT_PREVIEW_VISUAL` tag and `enforce_empty_not_zero`. `triggersGoldIngest` hardcoded to `False` throughout. No gold lines invented.

## 5. What looks solid
- **Honesty gates:** `is_empty_money` checks precede all math; `HONESTY_HALT` returned if coercion attempted.
- **No write-back:** No `UPDATE`/`INSERT` into SoftDent tables; read-only SQLite queries.
- **Flag-only behavior:** `thresholdViolated` is boolean flag only; no auto-correction logic.
- **Test coverage:** `test_null_visual_never_treated_as_zero` explicitly validates `None` ≠ `$0`.

## 6. Recommended fix order (if proceed) — small concrete patches, no greenfield redo
1. **Fix syntax:** Complete `visual_ledger_recon_widget` return statement (ship-blocking).
2. **Validate dates:** Add `try/except ValueError` in `parse_date_range` around `date()` construction.
3. **SQL safety:** Remove f-string from SQL in `sum_ledger_code2_payments`; use pure parameterized query.
4. **Precision:** Replace `delta_abs < 0.005` with `math.isclose(v, l, abs_tol=0.005)`.
5. **Scope warning:** Add `scopeMismatch` boolean to output when audit date range ≠ requested period.
6. **Perf:** Remove `TRIM(procedure)` if schema is trusted, or document functional index requirement.

## 7. Acceptance checks before merge-to-main confidence
- [ ] `python -c "from softdent_visual_ledger_recon import visual_ledger_recon_widget; print(visual_ledger_recon_widget())"` executes without `NameError`.
- [ ] `parse_date_range("2026-02-30")` returns `(None, None)` instead of raising.
- [ ] `classify_variance(None, 0.0)["result"] == "INSUFFICIENT_VISUAL"` and `delta` is `None`.
- [ ] `classify_variance(0.0, 0.0)["result"] == "MATCH"` (explicit zero equality).
- [ ] SQL query in `sum_ledger_code2_payments` contains no f-string literals (verify via `grep -n "f\"" softdent_visual_ledger_recon.py`).
- [ ] Unit test `test_end_to_end_temp_db_and_audit` passes with `100.0` vs `98.0` showing `VARIANCE_WITHIN_TOLERANCE`.
- [ ] Verify `triggersGoldIngest` is never `True` in any code path (grep confirms).