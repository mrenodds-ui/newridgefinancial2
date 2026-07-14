# Moonshot AI — What's Next After HAL-10592 Visual×Ledger Recon (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10592  
**Prior:** HAL-10592 visual×ledger recon (`2ababd5`) + review patches  
**Script:** `scripts/run_moonshot_whats_next_after_hal10592_consult.py`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> next

---

# Verdict
HAL-10593 / HON-003 — Visual×Ledger Recon Follow-ons: Carrier Spine Breakdown & Period Clamp (instrument the $52,389.57 variance signal just detected between $1.00 visual audit and $52,390.57 ledger spine without Gold CSV or ERA835).

## 0. Operator Intent (verbatim)
next

## 1. Recommended NEXT (name, why now, effort, REAL files/ops steps, validation gate)
**Name:** HAL-10593 / HON-003 — Visual×Ledger Recon Follow-ons: Carrier Breakdown & Period Clamp  
**Why now:** HAL-10592 just shipped and immediately flagged `VARIANCE_EXCEEDS_THRESHOLD` ($1.00 visual vs $52,390.57 ledger). Staff cannot act on this signal—and we cannot safely grow the 46-cell catalog—until we understand whether the variance stems from secondary-insurance inclusion, period-boundary leakage, or carrier-level scope drift. This package instruments the existing recon with granular carrier breakdowns (using the current InsCo×ADA spine) and defensive period clamping, providing the diagnostic layer missing between “flag variance” and “fix data.”  
**Effort:** 4–6 hours (SQL aggregation by carrier, defensive clamp logic, history persistence).  
**REAL files/ops steps:**
1. **Module:** `softdent_visual_ledger_recon.py` — add `sum_ledger_code2_by_carrier(period)`:
   - Query `ledger_spine` grouping by `ins_carrier_code` (46 exact usable cells only)
   - Return sorted list of (carrier, sum) contributing to the $52,390.57 total
   - SQL: parameterized `IN` clause for carrier codes (no f-strings, per HAL-10592 patch)
2. **Defensive clamp:** Add `clamp_ledger_to_audit_period(ledger_sum, audit_start, audit_end)`:
   - When `scopeMismatch=true`, re-query ledger restricted to audit date bounds
   - Surface `clampedLedgerTotal` in recon result (distinguishes period drift from true dollar drift)
3. **History table:** Migration `m_10593_recon_variance_history.sql`:
   - Columns: `period_start`, `period_end`, `visual_total`, `ledger_total`, `variance_dollars`, `top_carrier_code`, `scope_mismatch`, `created_at`
   - No PHI; aggregates only
4. **Widget:** `softdent-visual-ledger-recon` — add `carrierBreakdown` array (top 5 carriers by dollar contribution) and `clampedTotal` field
5. **CLI:** `scripts/audit_visual_ledger_variance.py` — add flags `--carrier-breakdown` and `--show-history-months=3`
6. **API:** `GET /api/apex/reconciliation/visual-ledger/history?months=` (read-only, paginated)  
**Validation gate:** Execute against live period 2026-06; verify carrier breakdown sums exactly to $52,390.57; simulate scopeMismatch by requesting period 2026-06-01..2026-06-30 against audit dated 2026-06-15..2026-06-30 and confirm clamp reduces ledger total appropriately; confirm `triggersGoldIngest` remains false; verify no new `gapCode` introduced.

## 2. Why this beats the other candidates now
- **Beats Candidate 1 (Honesty CI hardening):** The UI honesty layer is already passing 9/9 with zero failures; defensive contract tests are premature when an active, massive variance signal ($52k) demands immediate root-cause instrumentation.
- **Beats Candidate 3 (Catalog/spine reliability):** Expanding beyond the 46 exact usable cells (secondary-ins exclusion, same-day settlement logic) is risky without first validating that the existing 46-cell spine is correctly scoped. If the $52k includes out-of-period or secondary payments, growing the catalog will amplify the error. Instrument first, expand second.
- **Beats Candidate 4 (ERA835 first-drop):** The `eraLikeFilesSample` contains only manifests (no real 835 content); `era835` is null. Blocked until real payment content arrives.
- **Beats Candidate 2 (Staff UX polish):** Month-close checklists and carrier breakdown helpers are valuable only after the backend can actually explain the variance via carrier-level data. Candidate 7 provides the data prerequisite for Candidate 2.

## 3. Runner-ups (2–3, why not now)
1. **Candidate 3 — Catalog/spine reliability (secondary-ins exclusion, borderline-n bootstrap):** Growing the 46-cell catalog is the logical next step *after* we confirm the existing spine’s variance is understood. Defer one sprint to avoid baking scope errors into a larger dataset.
2. **Candidate 1 — Honesty CI gate hardening:** Financial widget regression testing (screenshot/contracts) should follow once the variance instrumentation proves the recon layer is stable; otherwise we risk hardening around a moving target.

## 4. What NOT to redo
- Do not re-implement HAL-10591 (empty≠$0) or HAL-10592 (visual×ledger recon base logic).
- No SoftDent write-back; remain flag-only.
- Do not invent Ins Plan Register dollars, carrier names, or gold payment lines.
- Do not trigger Gold CSV ingest (`triggersGoldIngest` stays false).
- Do not rebuild the TP chips, catalog, or spine from scratch; use the existing 46-cell spine for carrier breakdown.
- Do not re-export Register “Insurance Plan > 0” data.

## 5. Acceptance criteria
- Carrier breakdown query executes against June 2026 period, returning ≥1 rows summing to $52,390.57 without `ValueError` or SQL injection.
- `scopeMismatch` clamp logic tested: when audit `dateRange` is a subset of requested period, ledger sum recalculates to the narrower bounds and `clampedLedgerTotal` populates.
- `recon_variance_history` table persists last 3 months of variance snapshots (period, visual, ledger, variance, top carrier).
- Widget displays carrier breakdown using carrier codes only (no patient names, no account numbers).
- All SQL uses parameterized queries (no f-string interpolation, per HAL-10592 code-review patches).
- `triggersGoldIngest` remains `false` for all new endpoints; `gapCode` remains `GOLD_CSV_MISSING`.

## 6. Executive Summary (5 bullets)
- HAL-10592 detected a $52,389.57 variance between visual audit ($1.00) and ledger spine ($52,390.57); root cause is unknown.
- HAL-10593 instruments this variance by adding carrier-level granularity to the existing recon, using only the 46 exact usable cells already validated.
- Adds defensive period-clamping logic to distinguish true dollar drift from date-range scope mismatches.
- Establishes read-only variance history for multi-period trending without unblocking Gold CSV or ERA835.
- Maintains strict honesty policy: no SoftDent write-back, no $0 coercion, no gold fiction, no ERA manifests ingestion.

## 7. Approval checklist
- [ ] Operator confirms `era835` content remains null (manifests only, no real 835 payment data).
- [ ] Operator confirms Gold CSV still blocked (`gapCode=GOLD_CSV_MISSING`, `paymentLines=0`).
- [ ] Database migration for `recon_variance_history` reviewed: no PII, aggregate-only schema.
- [ ] Diff contains no SoftDent write-back operations (`INSERT`/`UPDATE` against `sd_*` tables).
- [ ] BUILD_ID set to `hal-10593` (decoupled from `hal-10592` package).