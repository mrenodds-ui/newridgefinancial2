# Moonshot AI — What's Next After HAL-10594 sql-null-honesty (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10594  
**Prior:** HAL-10594 sql-null-honesty (`6ce7028`)  
**Script:** `scripts/run_moonshot_whats_next_after_hal10594_consult.py`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> next

---

# Verdict
Recommended NEXT: **HAL-10595 / money-bridge-bijection** — replace IEEE-754 float bridge with string/cent-integer money serialization to close the HIGH severity bijective round-trip gap in API and history consumers.

## 0. Operator Intent (verbatim)
next

## 1. Recommended NEXT (name, why now, effort, REAL files/ops steps, validation gate)
**Package:** HAL-10595 / money-bridge-bijection  
**Why now:** HAL-10594 fixed SQL-layer NULL honesty, leaving the HIGH severity IEEE-754 float bridge (`money_to_api`) as the largest remaining compliance gap per the hardening consult. The `recon_variance_history` table currently stores `REAL` (approximate) floats; high-value orthodontic ledgers risk silent cent drift above 2^53 cents. This package hardens the money boundary before Gold CSV unblocks (preventing corrupt history accumulation) and completes the Decimal→SQL→API integrity chain started in 10591–10594.  
**Effort:** Small–Medium (1–2 days).  
**REAL files/ops steps:**  
1. **Schema migration** (`m_10595_money_exact.sql`): Add `money_cents_exact INTEGER` (or `TEXT` with decimal) to `recon_variance_history`; dual-write to new column while keeping `REAL` for backward compat during transition.  
2. **Code change** (`money_cents.py`): Add `money_to_api_bijective(value, format='cents_int')` → returns integer cents or string decimal; preserve legacy `money_to_api` for non-critical paths with deprecation warning.  
3. **API contract** (`api/apex/reconciliation.py`): Update `/visual-ledger/history` and widget endpoints to expose `total_cents` (int) alongside `total` (float) for consumers requiring exact arithmetic.  
4. **Migration** (`scripts/migrate_history_to_exact.py`): Backfill existing 3 history rows using original inputs (recompute from stored `period_start`/`end` + build_id) to populate `money_cents_exact` from source Decimal values, not from the lossy REAL column.  
5. **BUILD_ID bump:** `hal-10595` in `version.py` and package manifest.  
**Validation gate:** Property-based round-trip tests must pass for boundary values: `Decimal('0.01')`, `Decimal('999999.99')`, `Decimal('9007199254740993.00')` (2^53+1 cents), and random cent values. History query must return `total_cents` matching original ledger Decimal sum exactly; no variance between `Decimal(history.total_cents/100)` and source.

## 2. Why this beats the other candidates now
- **Beats CI gate (1):** 10594 already shipped with unit tests (`test_ledger_all_null_returns_none`). A CI gate is defensive regression insurance, but the float bridge is an active HIGH severity data-loss risk (per consult) affecting the 3 history rows already stored and all future reconciliations. Fixing the bridge is prerequisite to trustworthy history; testing a broken bridge is lower value.  
- **Beats Chain-of-custody (2):** History already has `record_fingerprint` (inputs-only) and UNIQUE INDEX fail-fast from 10594, providing tamper-evidence. Merkle chaining is MEDIUM severity enhancement; float precision is HIGH severity compliance gap.  
- **Beats ERA835 (4):** Ground truth confirms `gapCode: GOLD_CSV_MISSING` and `paymentLines: 0`. Without real 835 content or gold payment lines, ERA ingest would process empty sets, providing no validation value.  
- **Beats Catalog/spine (5):** Only 46 usable cells exist; growing secondary-ins and same-day settlement requires gold payment line ground truth to map carrier splits accurately. Blocked by same Gold CSV issue.  
- **Beats Async (7):** Latency optimization (ENH-001) does not address financial compliance or audit integrity risks.

## 3. Runner-ups (2–3, why not now)
1. **Honesty CI gate (candidate 1):** Valuable to prevent 10594 regression, but 10594 tests already cover the critical SQL null path. Defer until after float bridge is sealed to avoid testing a lossy serialization layer.  
2. **Audit chain-of-custody (candidate 2):** Adds `prev_fingerprint` and append-only triggers. Important for forensic audit, but current `record_fingerprint` + UNIQUE INDEX provides sufficient integrity for the 3 existing history rows; precision loss is the immediate threat.  
3. **ERA835 first-drop (candidate 4):** Requires real 835 content and gold payment lines to validate end-to-end. Currently blocked (`paymentLines: 0`); attempting now would require inventing test data rather than processing real operator files.

## 4. What NOT to redo
- Do not apply SoftDent write-back; remain flag-only.  
- Do not invent gold payment lines from ledger/DaySheet; wait for real Gold CSV.  
- Do not pretend Insurance Income Excel exists; `gapCode: GOLD_CSV_MISSING` remains honest.  
- Do not drift BUILD_ID; use `hal-10595`.  
- Do not reimplement 10591–10594 SQL/Decimal logic; build ON them.  
- Do not re-export Ins Plan Register dollars or carrier names.  
- Do not use COALESCE-to-zero in SQL aggregations (preserve 10594 NULL honesty).  
- Do not treat GitHub/PR workflow as the primary next deliverable; deliver code/ops packages.

## 5. Acceptance criteria
- [ ] `money_to_api_bijective` provides cent-integer and string-decimal paths with documented `ROUND_HALF_EVEN` parity.  
- [ ] `recon_variance_history` schema includes exact cent storage (INTEGER or TEXT) populated for all new rows.  
- [ ] Existing 3 history rows migrated or dual-written with exact cents recomputed from source inputs (not copied from lossy REAL).  
- [ ] API responses include `total_cents` integer field; float fields retained for backward compat but marked deprecated in docs.  
- [ ] Property tests verify bijective round-trip for 0.01, 999999.99, and 2^53+1 cent boundary.  
- [ ] BUILD_ID updated to `hal-10595`; package manifest references this consult.  
- [ ] No PHI columns added; `user_id`/`session_hash` explicitly excluded (PHI-safe), keeping only `record_fingerprint` for lineage.

## 6. Executive Summary (5 bullets)
- HAL-10594 closed the CRITICAL SQL NULL honesty gap; the remaining HIGH risk is the IEEE-754 float bridge in `money_to_api` used by history and API consumers.  
- Current `recon_variance_history` stores approximate REAL floats; orthodontic high-values (and any value >2^53 cents) suffer silent precision loss, violating cent-exact audit requirements.  
- HAL-10595 introduces string/cent-integer serialization, ensuring bijective Decimal↔API↔Decimal round-trips and eliminating float drift at the system boundary.  
- Package unblocks future Gold CSV ingest by guaranteeing that payment line amounts (when they arrive) are stored with cryptographic exactness, not JSON float approximations.  
- Validation relies on property-based round-trip tests and migration of existing 3 history rows; no SoftDent write-back or gold data invention required.

## 7. Approval checklist
- [ ] **Schema impact reviewed:** Confirm `money_cents_exact` column addition is backward compatible (dual-write strategy).  
- [ ] **API contract sign-off:** Consumers (visual widget, history endpoint) accept new `total_cents` integer field; frontend updated to use integer cents for display formatting if needed.  
- [ ] **Migration safety:** Script `migrate_history_to_exact.py` tested against production SQLite snapshot (3 rows) with WAL mode and `BEGIN IMMEDIATE`.  
- [ ] **Precision verification:** Unit tests demonstrate `Decimal(money_to_api_bijective(d, 'cents_int'))/100 == d` for all `d` in boundary set.  
- [ ] **BUILD_ID hygiene:** `hal-10595` set; no drift from 10594.  
- [ ] **PHI boundary check:** Confirm no patient/account identifiers added to history schema; `record_fingerprint` remains inputs-only hash.  
- [ ] **Gold CSV status:** Acknowledge `gapCode: GOLD_CSV_MISSING` persists; this package does not require gold unblocking but prepares the ledger for it.