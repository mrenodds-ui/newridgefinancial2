# Moonshot AI — Uniform ADA Analysis + Treatment Planning (CONSULT ONLY)

**Date:** 2026-07-13  
**Model:** kimi-k2.5  
**Key:** OPENROUTER_API_KEY  
**Status:** ok  
**Build:** hal-10576  
**Prior:** HAL-10584 InsCo×ADA % +/- (`5f7fb56`)  
**Script:** `scripts/run_moonshot_uniform_ada_treatment_planning_consult.py`  
**Apply:** DO NOT APPLY until operator approves (`proceed`).

## Operator request (verbatim)

> all ada codes should be analzyed the same way and consult with moonoshot ai for reference and recommendation and also for treatment planning with the program

---

# Verdict
Unify the ADA analysis spine (converge HAL-10582/84 into a single episode-pairing pipeline) and wire it into treatment planning as the fallback when gold payment lines are absent, with ordered steps: (1) normalize 5-year episode logic across $ and % tables, (2) expose the unified matrix to the treatment-planning estimator with credibility badges.

## 0. Operator Intent (verbatim)
> "all ada codes should be analzyed the same way and consult with moonoshot ai for reference and recommendation and also for treatment planning with the program"

## 1. Recommended NEXT (name, why now, effort, REAL files, validation gate)
**Name:** Unified InsCo×ADA Analysis Spine + Treatment Planning Fallback  
**Why now:** HAL-10584 (%) and HAL-10582 ($) currently use divergent lookback windows (5-year vs ~24-month) and divergent normalization (10584 pads 3-digit codes to D0xxx; 10582 uses `normalize_ada_code` only). This violates the “same way” mandate. Meanwhile, `treatment_planning_estimates` remains at zero rows, leaving the program with no estimate path. Unifying the spine first ensures the fallback data is consistent; wiring it second closes the UX gap.  
**Effort:** Medium (3–4 days). Local refactor + HAL widget update; no SoftDent write-back.  
**REAL files:**  
- New: `softdent_insco_ada_spine.py` (shared episode builder, 5-year window, exact/inferred classifier)  
- Refactor: `softdent_insco_ada_pct_variance.py` → consume spine; `softdent_insco_ada_probabilistic.py` → consume spine (replace 24mo standalone logic)  
- Extend: `softdent_treatment_planning.py` → `lookup_treatment_estimate` adds fallback query to spine when `sd_insurance_payment_lines` COUNT=0  
- HAL: `nr2_hal_gateway.py` intent `policy:treatment-estimate` updated to surface spine-derived estimates with badges  
**Validation gate:**  
- Both $ and % outputs derive from identical episode sets (same `episode_id` list for a given InsCo×ADA).  
- Treatment planning API returns `estimated_pay`, `estimated_writeoff`, `pay_pct`, `wo_pct`, `credibility_tier`, `n_sample`, `source='ledger_episode_5yr'` when gold path empty; returns gold data when available.  
- Internal SoftDent codes (12, 61, 8888, decimals) are excluded from the ADA matrix or explicitly mapped to CDT before analysis.

## 2. Uniform ADA analysis reference (how every code is treated identically)
Every production CDT code traverses the same pipeline:
1. **Window:** 5-year lookback (`2021-07-13` → today) for all metrics, replacing the 24-month limit in probabilistic $.  
2. **Normalization:** Standardize to D-format (D####) via a single `normalize_cdt` utility; reject non-CDT patterns (internal codes 2, 51, 12, 61, 8888, decimals) from the production side—they remain valid as payment/write-off codes only.  
3. **Episode pairing:** Production charge cluster (same account, within 7 days) → forward SoftDent codes **2** (insurance pay), **51/52** (write-off) within 60 days or until next production charge.  
4. **Classification:**  
   - **Exact:** Single ADA in the production cluster.  
   - **Inferred:** Multi-ADA cluster → allocate 2/51/52 dollars by billed share (flagged as inferred).  
5. **Metrics:** Calculate median $ (paid, WO) **and** median % (of billed) with 1 population SD for +/-.  
6. **Credibility:** Same thresholds for both $ and %:  
   - High: exact n≥30  
   - Usable: exact n≥10 or inferred n≥30  
   - Low: never published  
   - Insufficient: honest null (empty ≠ $0).  

## 3. Treatment planning integration (program path when gold empty)
When `treatment_planning_estimates` and `sd_insurance_payment_lines` are empty (current state):
- **Fallback query:** `lookup_treatment_estimate(carrier, ada)` queries the unified spine for the InsCo×ADA cell.  
- **Return payload:**  
  ```json
  {
    "estimated_pay": 45.50,
    "estimated_writeoff": 23.63,
    "pay_percentage": 45.87,
    "wo_percentage": 23.63,
    "credibility": "high",
    "sample_size": 172,
    "source": "ledger_episode_5yr",
    "is_inferred": false,
    "gold_available": false
  }
  ```
- **Honesty badges:**  
  - Green “High confidence (n≥30)”  
  - Amber “Usable history (n≥10)”  
  - Red “Inferred allocation (multi-procedure episode)” — hidden behind “Show uncertain” toggle  
  - Gray “Insufficient data” — empty field, never $0.  
- **Gold preference:** If payment lines later appear, gold path automatically overrides spine fallback (no code change required, just data presence).

## 4. Runner-ups (2–3, why not now)
- **Candidate 3 (Full CDT catalog matrix UI):** Visibility of all 253 distinct procedures is valuable, but premature while $ and % pipelines diverge. Ship after spine unification to avoid displaying conflicting numbers.  
- **Candidate 5 (SoftDent-internal code map):** Necessary hygiene (mapping 12/61/8888/decimals to CDT or exclusion), but should be implemented *inside* the unified spine rather than as a standalone package.  
- **Candidate 4 (Insurance Payment Analysis → gold path):** Blocked by operational reality (operator notes Excel often unavailable). Revisit only when SoftDent enables automated CSV export of `Insurance Payment Analysis`.

## 5. What NOT to redo
- SoftDent write-back (no updates to SoftDent tables).  
- Invent $0 for empty cells (return explicit null/“insufficient”).  
- Claim contractual fee schedule (source remains ledger history, not Plan Register).  
- Register re-export for Ins Plan > 0.  
- Pretend gold path exists (treatment planning must handle the zero-row case explicitly).

## 6. Acceptance criteria
- [ ] `softdent_insco_ada_spine.py` produces identical episode lists for both $ and % exports (diff ≤0.1% episode count).  
- [ ] All published InsCo×ADA cells (currently 46 exact + inferred in %, 124 in $) derive from the same 5-year episode set.  
- [ ] `softdent_treatment_planning.py` returns spine-derived estimates with `source='ledger_episode_5yr'` when gold tables empty.  
- [ ] Internal codes (12, 61, 8888, decimals) do not appear as rows in the ADA matrix unless explicitly mapped to CDT.  
- [ ] HAL widget displays credibility badges and hides “low” tier entirely; “inferred” requires user opt-in toggle.  
- [ ] Unit tests verify `empty != $0` (assert `None` or missing key, not `0.00`).

## 7. Executive Summary (5 bullets)
- **Converge first:** Unify HAL-10582 ($) and HAL-10584 (%) into a single 5-year episode-pairing spine so every ADA is analyzed identically.  
- **Treatment planning fallback:** Wire the unified spine into `lookup_treatment_estimate` as the default when gold payment lines are absent, preventing silent $0 invention.  
- **Honesty badges:** Surface credibility (high/usable/inferred/insufficient) in the program UX so staff know when estimates are based on proportional allocation vs. exact history.  
- **Data hygiene:** Filter SoftDent internal codes (12, 61, 8888, decimals) at the spine level—treat them as payment events, not production ADAs.  
- **Gold path preserved:** When `sd_insurance_payment_lines` eventually populate, they automatically take precedence over ledger-derived estimates without code changes.

## 8. Approval checklist
- [ ] Operator confirms 5-year window acceptable for both $ and % (vs. 24-month).  
- [ ] Operator approves excluding unmapped internal codes (12, 61, 8888, decimals) from ADA matrix rows.  
- [ ] Operator accepts “inferred” estimates require UI toggle (not shown by default).  
- [ ] Dev confirms no SoftDent write-back required.  
- [ ] QA confirms empty estimates return `null`, not `$0.00`.