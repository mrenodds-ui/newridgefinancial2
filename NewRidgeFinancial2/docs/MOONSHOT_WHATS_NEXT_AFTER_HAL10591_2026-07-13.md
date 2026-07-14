# Moonshot AI — What's Next After HAL-10591 UI Honesty (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10591  
**Prior:** HAL-10591 empty≠$0 UI honesty (`1c1d431`)  
**Script:** `scripts/run_moonshot_whats_next_after_hal10591_consult.py`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> next

---

# Verdict
**HAL-10592 / HON-002 — Visual-Audit × Ledger Spine Reconciliation**: Compare Print Preview Insurance Income aggregates to the 46-cell probabilistic ledger spine period sums, flag variance thresholds without inventing gold payment lines, building directly atop HAL-10591’s honesty enforcement to validate the drift between visual staff audits and the InsCo×ADA fallback model.

## 0. Operator Intent (verbatim)
next

## 1. Recommended NEXT (name, why now, effort, REAL files/ops steps, validation gate)
**Name:** HAL-10592 / HON-002 — Visual-Audit × Ledger Spine Reconciliation  
**Why now:** HAL-10590 established PHI-safe visual audit totals (e.g., `$1.0` last-page aggregates) and HAL-10591 hardened the honesty layer to prevent empty→$0.00 coercion. However, we have no validation whether these visual staff-recorded totals align with the probabilistic InsCo×ADA ledger spine (46 exact usable cells from HAL-10580–10587). This reconciliation detects drift between ground-truth visual aggregates and the fallback model *without* requiring the blocked Gold CSV, providing the first honest variance signal in the data pipeline.

**Effort:** 6–8 hours (reconciliation engine, variance policy, HAL wiring).

**REAL files/ops steps:**
1. **Reconciler Module:** `apex/reconciliation/visual_ledger_recon.py` — `VisualLedgerReconciler` class:
   - Input: `print_preview_audit_log.jsonl` (HAL-10590) filtered by `reportType=InsuranceIncome` and `dateRange`
   - Input: `ledger_spine.probabilisticPeriodSum` (InsCo×ADA 46-cell catalog) by matching period
   - Logic: Compare `lastPageAggregateTotal` vs `probabilisticSum`; compute delta
   - Threshold config: `VARIANCE_THRESHOLD_ABSOLUTE=5.00`, `VARIANCE_THRESHOLD_PERCENT=5.0`
   - Output: `ReconciliationResult` enum (`MATCH`, `VARIANCE_WITHIN_TOLERANCE`, `VARIANCE_EXCEEDS_THRESHOLD`)

2. **HAL Policy:** `hal/policy/hon_002_visual_ledger_variance.yaml`:
   - Bind to `apex.reconciliation.visual_ledger`
   - Action: `flag_not_fix` (alert only; never auto-correct or invent payment lines)
   - Honesty check: Verify HAL-10591 `enforce_empty_not_zero` is active on both inputs before comparison

3. **API Surface:** `GET /api/apex/reconciliation/visual-ledger/status?period=2026-06`:
   - Returns `visualTotal`, `ledgerTotal`, `delta`, `thresholdViolated`, `honestyCheckPassed`

4. **Widget:** `visual-ledger-variance` (React/Vue):
   - Display: ✅ Match, ⚠️ Variance $X (>threshold), or — (insufficient data)
   - Drill-down: Carrier breakdown from ledger spine if available; visual audit source tag badge
   - Tooltip: “Comparison between staff visual audit and probabilistic ledger; does not create payment lines”

5. **CLI:** `scripts/audit_visual_ledger_variance.py` — weekly operator report of mismatched periods

6. **CI Test:** `test_hal10592_visual_ledger_recon.py`:
   - Mock visual audit `$100.00` vs ledger `$98.00` → PASS (within 5%)
   - Mock visual audit `$100.00` vs ledger `$50.00` → FLAG (exceeds threshold)
   - Mock visual audit `null` vs ledger `$0.00` → HALT (HON-001 violation detection)

**Validation gate:**
- [ ] Unit tests pass for threshold logic (absolute and percent)
- [ ] Integration test confirms HAL-10591 policy prevents null visual totals from being treated as $0.00 in reconciliation math
- [ ] Staging run against live `print_preview_audit_log.jsonl` shows 0 invented paymentLines in database
- [ ] BUILD_ID `hal-10592` coupled to changes

## 2. Why this beats the other candidates now
- **#2 ERA835 first-drop:** Blocked by reality — `era835: null` in snapshot, only manifests exist. Cannot process what does not exist.
- **#3 Catalog/spine reliability:** Premature expansion. Growing beyond 46 cells without validating against ground truth (visual audit) risks compounding fallback errors. Reconcile first, then grow.
- **#4 Uncovered ledger CDT playbook:** Narrower scope; reconciliation covers the aggregate mismatch that CDTs contribute to.
- **#5 Async HAL / ASGI queue:** Infrastructure latency is not the constraint; data famine is. This does not unblock the data plane.
- **#6 Staff Print Preview UX polish:** Operational convenience is secondary to data integrity validation. Reconciliation provides the “why” for any UX alerts.
- **#7 Honesty CI gate hardening:** Defensive and important, but passive. Reconciliation is an active validation that exercises the honesty layer in production with real data (visual vs. ledger), providing immediate RCM value while testing HON-001 under load.

## 3. Runner-ups (2–3, why not now)
1. **#7 Honesty CI gate hardening:** Critical for long-term regression safety, but should follow HON-002 to ensure the reconciliation logic itself is what gets hardened, not just generic widgets. Defer to HAL-10593.
2. **#6 Staff Print Preview audit UX polish:** Carrier breakdown helper and month-close checklist are operational force-multipliers, but only valuable if staff trusts the underlying variance detection (which HON-002 provides). Defer until reconciliation baseline established.
3. **#3 Catalog/spine reliability (borderline-n bootstrap):** The 46 exact cells are sufficient for the reconciliation test. Expanding the catalog now without ground-truth validation risks “garbage in, gospel out.” Defer until HON-002 validates the spine’s accuracy against visual audits.

## 4. What NOT to redo
- **SoftDent write-back** of any kind (no adjustments to SoftDent ledger)
- **Invent gold payment lines** from DaySheet, ledger, or visual audit totals
- **Re-implement HON-001** (empty≠$0 enforcement) — assume HAL-10591 is production and build on it
- **Greenfield redo** of TP chips, InsCo×ADA catalog, or Print Preview audit (HAL-10580–10591 are shipped; extend them)
- **ERA835 processing** until real 835 content exists (not just manifests)
- **ASGI/Async queue** infrastructure (not data-critical path)
- **GitHub/PR mechanics** as the primary next step

## 5. Acceptance criteria
- [ ] `VisualLedgerReconciler` correctly matches `print_preview_visual` aggregates to `ledger_spine` probabilistic sums by month period
- [ ] Variance detection honors HAL-10591 honesty: null visual totals are excluded from comparison, never treated as $0.00
- [ ] No `sd_insurance_payment_lines` records created or modified in any database (visual audit remains non-ingest)
- [ ] HAL policy `hon_002` triggers alert on variance >$5 or >5%, but does not auto-correct
- [ ] BUILD_ID `hal-10592` coupled and immutable
- [ ] `gapCode` remains `GOLD_CSV_MISSING`; `paymentLines` remains `0` (honesty preserved)

## 6. Executive Summary (5 bullets)
- **Ground-truth validation:** Compares staff-visual aggregates (HAL-10590) against the probabilistic ledger spine (HAL-10580–10587) to detect model drift without waiting for blocked Gold CSV.
- **Honesty extension:** Actively exercises HAL-10591’s empty≠$0 enforcement in production reconciliation logic, ensuring nulls propagate as nulls through variance calculations.
- **Zero-invention policy:** Flags discrepancies for human review; never auto-generates payment lines or carrier assignments, maintaining `paymentLines=0` integrity.
- **Risk reduction:** Identifies whether the 46-cell InsCo×ADA fallback is underestimating/overestimating actual Insurance Income before expanding catalog coverage.
- **Foundation for unblock:** When ERA835 or Gold CSV eventually arrives, this reconciliation framework provides the validation layer to confirm their accuracy against established visual baselines.

## 7. Approval checklist
- [ ] Effort 6–8h acceptable for variance detection MVP
- [ ] No SoftDent write-back or database mutation required
- [ ] No invention of insurance payment lines or carrier names
- [ ] Builds directly on HAL-10591 (HON-001) honesty layer
- [ ] PHI-safe (aggregates only, no patient-level data)
- [ ] Compatible with `gapCode=GOLD_CSV_MISSING` state
- [ ] BUILD_ID `hal-10592` coupling confirmed